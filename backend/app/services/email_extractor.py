import re
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
EXCLUDE_DOMAINS = {
    "example.com", "yourdomain.com", "sentry.io", "wixpress.com",
    "wordpress.com", "squarespace.com", "godaddy.com", "domain.com",
    "email.com", "youremail.com", "placeholder.com",
}
CONTACT_PATHS = [
    "/contact", "/contact-us", "/contact_us",
    "/about", "/about-us", "/about_us",
    "/team", "/our-team", "/staff",
]
PRIORITY_PREFIXES = ["info", "contact", "hello", "support", "admin"]

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

    return None


def _extract_from_html(html: str, base_domain: str) -> list[str]:
    # Use stdlib html.parser — lower CPU/memory than lxml on small capped documents
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

    # Filter false positives
    filtered = [
        e for e in emails
        if e.split("@")[-1] not in EXCLUDE_DOMAINS
        and "." in e.split("@")[-1]
    ]

    return filtered


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
