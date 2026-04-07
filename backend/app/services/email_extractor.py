import re
import logging
from urllib.parse import urljoin, urlparse, quote_plus
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
EXCLUDE_DOMAINS = {
    "example.com", "yourdomain.com", "sentry.io", "wixpress.com",
    "wordpress.com", "squarespace.com", "godaddy.com", "domain.com",
    "email.com", "youremail.com", "placeholder.com", "gmail.com",
    "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "googleusercontent.com", "gstatic.com", "w3.org",
}
CONTACT_PATHS = [
    "/contact", "/contact-us", "/contact_us",
    "/about", "/about-us", "/about_us",
    "/team", "/our-team", "/staff",
    "/info", "/get-in-touch",
]
PRIORITY_PREFIXES = ["info", "contact", "hello", "support", "admin", "office", "sales"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

HTML_SIZE_LIMIT = 50 * 1024  # 50 KB


async def extract_email(url: str, homepage_html: str, client: httpx.AsyncClient) -> str | None:
    """Extract the best contact email from a business website."""
    base_domain = urlparse(url).netloc.lower().removeprefix("www.")

    # 1. Try homepage HTML first (already fetched and capped during evaluation)
    emails = _extract_from_html(homepage_html, base_domain)
    if emails:
        return _pick_best(emails, base_domain)

    # 2. Discover contact-like links from homepage nav
    extra_paths = _discover_contact_paths(homepage_html, url)
    all_paths = list(dict.fromkeys(CONTACT_PATHS + extra_paths))  # dedup, preserve order

    # 3. Try contact/about pages — stream with 50KB cap
    for path in all_paths:
        contact_url = urljoin(url, path)
        try:
            async with client.stream("GET", contact_url, timeout=8.0, follow_redirects=True) as resp:
                if resp.status_code != 200:
                    continue
                chunks: list[bytes] = []
                size = 0
                async for chunk in resp.aiter_bytes(4096):
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= HTML_SIZE_LIMIT:
                        break
                contact_html = b"".join(chunks).decode("utf-8", errors="replace")
            emails = _extract_from_html(contact_html, base_domain)
            if emails:
                return _pick_best(emails, base_domain)
        except httpx.RequestError:
            continue

    # 4. Check footer specifically — many sites hide emails in footer only
    email = _extract_from_footer(homepage_html, base_domain)
    if email:
        return email

    return None


async def find_email_for_lead(business_name: str, city: str, state: str,
                               website_url: str | None = None,
                               phone: str | None = None) -> dict:
    """Deep email search for a single lead — tries multiple strategies.

    Returns {"email": "...", "source": "..."} or {"email": None, "source": "not_found"}
    """
    async with httpx.AsyncClient(headers=HEADERS, timeout=12.0, follow_redirects=True) as client:

        # Strategy 1: Scrape the business website if available
        if website_url:
            try:
                resp = await client.get(website_url)
                if resp.status_code == 200:
                    html = resp.text[:HTML_SIZE_LIMIT]
                    email = await extract_email(website_url, html, client)
                    if email:
                        return {"email": email, "source": "website"}
            except httpx.RequestError:
                pass

        # Strategy 2: Google search for the business email
        email = await _google_search_email(business_name, city, state, client)
        if email:
            return {"email": email, "source": "google"}

        # Strategy 3: Search Yelp listing page for email
        email = await _yelp_listing_email(business_name, city, state, client)
        if email:
            return {"email": email, "source": "yelp_listing"}

        # Strategy 4: Search BBB listing for email
        email = await _bbb_listing_email(business_name, city, state, client)
        if email:
            return {"email": email, "source": "bbb_listing"}

        # Strategy 5: Try Yellow Pages listing
        email = await _yp_listing_email(business_name, city, state, client)
        if email:
            return {"email": email, "source": "yellowpages_listing"}

        # Strategy 6: If we have a website domain, try common patterns
        if website_url:
            domain = urlparse(website_url).netloc.lower().removeprefix("www.")
            email = await _try_common_patterns(domain, client)
            if email:
                return {"email": email, "source": "common_pattern"}

    return {"email": None, "source": "not_found"}


async def bulk_find_emails(leads: list[dict]) -> list[dict]:
    """Find emails for multiple leads. Returns list of {lead_id, email, source}."""
    import asyncio
    sem = asyncio.Semaphore(3)  # be polite
    results = []

    async def _find_one(lead: dict):
        async with sem:
            result = await find_email_for_lead(
                business_name=lead["business_name"],
                city=lead["city"],
                state=lead["state"],
                website_url=lead.get("website_url"),
                phone=lead.get("phone"),
            )
            return {"lead_id": lead["id"], **result}

    results = await asyncio.gather(
        *[_find_one(lead) for lead in leads],
        return_exceptions=True,
    )

    return [r for r in results if isinstance(r, dict)]


async def _google_search_email(name: str, city: str, state: str,
                                client: httpx.AsyncClient) -> str | None:
    """Search Google for the business and look for email addresses in results."""
    query = quote_plus(f'"{name}" "{city}" "{state}" email contact')
    url = f"https://www.google.com/search?q={query}&num=5"
    try:
        resp = await client.get(url, headers={
            **HEADERS,
            "Accept": "text/html,application/xhtml+xml",
        })
        if resp.status_code != 200:
            return None
        html = resp.text[:HTML_SIZE_LIMIT]
        emails = _filter_emails(EMAIL_REGEX.findall(html))
        if emails:
            return _pick_best_generic(emails)
    except httpx.RequestError:
        pass
    return None


async def _yelp_listing_email(name: str, city: str, state: str,
                               client: httpx.AsyncClient) -> str | None:
    """Search Yelp for the business and scrape listing for email."""
    query = quote_plus(f"{name}")
    location = quote_plus(f"{city}, {state}")
    url = f"https://www.yelp.com/search?find_desc={query}&find_loc={location}"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text[:HTML_SIZE_LIMIT], "html.parser")
        # Find the first listing link
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "/biz/" in href and "?" not in href:
                listing_url = f"https://www.yelp.com{href}" if href.startswith("/") else href
                listing_resp = await client.get(listing_url)
                if listing_resp.status_code == 200:
                    emails = _filter_emails(EMAIL_REGEX.findall(listing_resp.text[:HTML_SIZE_LIMIT]))
                    if emails:
                        return _pick_best_generic(emails)
                break  # only try first result
    except httpx.RequestError:
        pass
    return None


async def _bbb_listing_email(name: str, city: str, state: str,
                              client: httpx.AsyncClient) -> str | None:
    """Search BBB for the business and scrape for email."""
    query = quote_plus(f"{name}")
    location = quote_plus(f"{city}, {state}")
    url = f"https://www.bbb.org/search?find_country=US&find_text={query}&find_loc={location}"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text[:HTML_SIZE_LIMIT], "html.parser")
        # Look for listing links
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "/profile/" in href or "/accredited-business/" in href:
                listing_url = href if href.startswith("http") else f"https://www.bbb.org{href}"
                listing_resp = await client.get(listing_url)
                if listing_resp.status_code == 200:
                    emails = _filter_emails(EMAIL_REGEX.findall(listing_resp.text[:HTML_SIZE_LIMIT]))
                    if emails:
                        return _pick_best_generic(emails)
                break
    except httpx.RequestError:
        pass
    return None


async def _yp_listing_email(name: str, city: str, state: str,
                             client: httpx.AsyncClient) -> str | None:
    """Search Yellow Pages for the business and scrape for email."""
    query = quote_plus(f"{name}")
    location = quote_plus(f"{city}, {state}")
    url = f"https://www.yellowpages.com/search?search_terms={query}&geo_location_terms={location}"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text[:HTML_SIZE_LIMIT], "html.parser")
        # Try to find listing detail links
        for a_tag in soup.select("a.business-name"):
            href = a_tag.get("href", "")
            if href:
                listing_url = f"https://www.yellowpages.com{href}" if href.startswith("/") else href
                listing_resp = await client.get(listing_url)
                if listing_resp.status_code == 200:
                    listing_html = listing_resp.text[:HTML_SIZE_LIMIT]
                    # YP sometimes has email links
                    emails = _filter_emails(EMAIL_REGEX.findall(listing_html))
                    if emails:
                        return _pick_best_generic(emails)
                    # Also check mailto links
                    listing_soup = BeautifulSoup(listing_html, "html.parser")
                    for mailto in listing_soup.find_all("a", href=True):
                        if mailto["href"].startswith("mailto:"):
                            email = mailto["href"][7:].split("?")[0].strip().lower()
                            if email and email.split("@")[-1] not in EXCLUDE_DOMAINS:
                                return email
                break
    except httpx.RequestError:
        pass
    return None


async def _try_common_patterns(domain: str, client: httpx.AsyncClient) -> str | None:
    """Try common email prefixes against the domain — verify with a simple check."""
    if not domain or "." not in domain:
        return None

    # We can't truly verify emails without SMTP, but we can try common ones
    # and see if they appear anywhere on the web
    common = [f"info@{domain}", f"contact@{domain}", f"hello@{domain}",
              f"office@{domain}", f"admin@{domain}", f"sales@{domain}"]

    # Quick Google check for these emails
    for email in common[:3]:  # only try top 3 to be polite
        query = quote_plus(f'"{email}"')
        url = f"https://www.google.com/search?q={query}"
        try:
            resp = await client.get(url, headers={
                **HEADERS,
                "Accept": "text/html,application/xhtml+xml",
            })
            if resp.status_code == 200 and email in resp.text.lower():
                return email
        except httpx.RequestError:
            continue

    return None


def _extract_from_html(html: str, base_domain: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")

    emails: set[str] = set()

    # Regex on visible text
    text = soup.get_text()
    for match in EMAIL_REGEX.findall(text):
        emails.add(match.lower())

    # mailto: hrefs
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith("mailto:"):
            email = href[7:].split("?")[0].strip().lower()
            if email:
                emails.add(email)

    # Check meta tags (some sites put email in meta)
    for meta in soup.find_all("meta"):
        content = meta.get("content", "")
        for match in EMAIL_REGEX.findall(content):
            emails.add(match.lower())

    # Filter false positives
    filtered = [
        e for e in emails
        if e.split("@")[-1] not in EXCLUDE_DOMAINS
        and "." in e.split("@")[-1]
        and not e.endswith(".png")
        and not e.endswith(".jpg")
        and not e.endswith(".svg")
        and len(e) < 80
    ]

    return filtered


def _extract_from_footer(html: str, base_domain: str) -> str | None:
    """Some sites only have email in footer elements."""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    footer = soup.find("footer") or soup.find(id="footer") or soup.find(class_="footer")
    if not footer:
        return None
    footer_text = footer.get_text()
    emails = EMAIL_REGEX.findall(footer_text)
    # Also check mailto in footer
    for a_tag in footer.find_all("a", href=True):
        if a_tag["href"].startswith("mailto:"):
            email = a_tag["href"][7:].split("?")[0].strip().lower()
            if email:
                emails.append(email)
    filtered = _filter_emails(emails)
    if filtered:
        return _pick_best(filtered, base_domain)
    return None


_CONTACT_KEYWORDS = re.compile(r"contact|email|reach|get\s+in\s+touch", re.IGNORECASE)


def _discover_contact_paths(html: str, base_url: str) -> list[str]:
    """Scan homepage <a> tags for links whose text suggests a contact page."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    parsed_base = urlparse(base_url)
    paths: list[str] = []
    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True)
        if not text or not _CONTACT_KEYWORDS.search(text):
            continue
        href = a_tag["href"]
        parsed = urlparse(href)
        # Only follow same-domain or relative links
        if parsed.netloc and parsed.netloc.replace("www.", "") != parsed_base.netloc.replace("www.", ""):
            continue
        path = parsed.path
        if path and path != "/" and path not in paths:
            paths.append(path)
    return paths


def _filter_emails(emails: list[str]) -> list[str]:
    """Filter a raw list of email matches to remove junk."""
    return [
        e.lower() for e in emails
        if e.split("@")[-1].lower() not in EXCLUDE_DOMAINS
        and "." in e.split("@")[-1]
        and not e.lower().endswith((".png", ".jpg", ".svg", ".gif", ".css", ".js"))
        and len(e) < 80
        and "@" in e
    ]


def _pick_best(emails: list[str], base_domain: str) -> str:
    # Prefer emails at the business's own domain
    own_domain = [e for e in emails if base_domain in e]
    pool = own_domain if own_domain else emails

    # Prefer priority prefixes
    for prefix in PRIORITY_PREFIXES:
        for email in pool:
            if email.startswith(prefix + "@"):
                return email

    return pool[0]


def _pick_best_generic(emails: list[str]) -> str:
    """Pick best email when we don't know the base domain."""
    # Prefer business-like prefixes
    for prefix in PRIORITY_PREFIXES:
        for email in emails:
            if email.lower().startswith(prefix + "@"):
                return email.lower()
    return emails[0].lower()
