"""Deep research module — extracts rich data from raw scraped data and business websites."""

import re
import logging
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

HTML_SIZE_LIMIT = 200 * 1024  # 200 KB

# Patterns for discovering contact names
_TITLE_KEYWORDS = re.compile(
    r"\b(owner|founder|ceo|president|manager|director|principal|proprietor|partner)\b",
    re.IGNORECASE,
)
_NAME_PATTERN = re.compile(
    r"(?:^|[,\-–—:|\n])\s*([A-Z][a-z]{1,15}(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]{1,20})\s*(?:[,\-–—:|]|$)"
)

_PHONE_REGEX = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
)
_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "instagram.com": "instagram",
    "linkedin.com": "linkedin",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "youtube.com": "youtube",
    "tiktok.com": "tiktok",
    "yelp.com": "yelp",
}

_JUNK_EMAIL_DOMAINS = {
    "example.com", "yourdomain.com", "sentry.io", "wixpress.com",
    "wordpress.com", "squarespace.com", "godaddy.com", "domain.com",
    "email.com", "youremail.com", "placeholder.com",
    "googleusercontent.com", "gstatic.com", "w3.org",
}

_ABOUT_PATHS = [
    "/about", "/about-us", "/about_us",
    "/team", "/our-team", "/staff",
    "/leadership", "/management",
]


def extract_from_raw_data(biz: dict) -> dict:
    """Extract structured fields from raw_data without any HTTP calls.

    Works for all sources — parses Yelp API responses, BBB data, etc.
    """
    enrichment: dict = {}
    raw = biz.get("raw_data") or {}
    source = biz.get("source", "")

    if source == "yelp":
        # Yelp API response fields
        enrichment["rating"] = raw.get("rating")
        enrichment["review_count"] = raw.get("review_count")

        categories = raw.get("categories", [])
        if categories:
            enrichment["yelp_categories"] = [c.get("title", "") for c in categories if c.get("title")]

        location = raw.get("location", {})
        display_address = location.get("display_address", [])
        if display_address:
            enrichment["address"] = ", ".join(display_address)

        # Yelp sometimes includes hours
        hours = raw.get("hours", [])
        if hours:
            enrichment["business_hours"] = _format_yelp_hours(hours)

    elif source == "bbb":
        enrichment["bbb_accredited"] = raw.get("accreditationStatus") == "ACCREDITED" or raw.get("isAccredited", False)
        if raw.get("rating"):
            # BBB ratings are letter grades, not numbers — skip for numeric field
            pass
        if raw.get("yearsInBusiness"):
            try:
                enrichment["years_in_business"] = int(raw["yearsInBusiness"])
            except (ValueError, TypeError):
                pass
        if raw.get("address"):
            enrichment["address"] = raw["address"]

    elif source in ("yellowpages", "superpages", "manta"):
        if raw.get("address"):
            enrichment["address"] = raw["address"]

    # Filter out None values
    return {k: v for k, v in enrichment.items() if v is not None}


async def deep_research(biz: dict, homepage_html: str, client: httpx.AsyncClient) -> dict:
    """HTTP-based deep research on a business website.

    Extracts: contact names, social links, additional emails/phones, business hours.
    """
    enrichment: dict = {
        "additional_phones": [],
        "additional_emails": [],
        "social_links": {},
    }

    website_url = biz.get("website_url", "")
    if not website_url:
        return enrichment

    base_domain = urlparse(website_url).netloc.lower().removeprefix("www.")

    # Parse homepage
    soup = BeautifulSoup(homepage_html, "html.parser") if homepage_html else None

    if soup:
        # Extract social links from homepage
        enrichment["social_links"] = _extract_social_links(soup, website_url)

        # Extract all phones and emails from homepage
        all_phones = _extract_all_phones(soup, biz.get("phone"))
        all_emails = _extract_all_emails(soup, biz.get("email"), base_domain)
        enrichment["additional_phones"] = all_phones
        enrichment["additional_emails"] = all_emails

        # Try to find contact name from homepage
        contact = _find_contact_in_html(soup)
        if contact:
            enrichment["contact_name"] = contact.get("name")
            enrichment["contact_title"] = contact.get("title")

        # Extract business hours from JSON-LD
        hours = _extract_jsonld_hours(soup)
        if hours:
            enrichment["business_hours"] = hours

    # If no contact found yet, try about/team pages
    if not enrichment.get("contact_name"):
        for path in _ABOUT_PATHS:
            about_url = urljoin(website_url, path)
            try:
                async with client.stream("GET", about_url, timeout=8.0, follow_redirects=True) as resp:
                    if resp.status_code != 200:
                        continue
                    chunks = []
                    size = 0
                    async for chunk in resp.aiter_bytes(4096):
                        chunks.append(chunk)
                        size += len(chunk)
                        if size >= HTML_SIZE_LIMIT:
                            break
                    about_html = b"".join(chunks).decode("utf-8", errors="replace")

                about_soup = BeautifulSoup(about_html, "html.parser")
                contact = _find_contact_in_html(about_soup)
                if contact:
                    enrichment["contact_name"] = contact.get("name")
                    enrichment["contact_title"] = contact.get("title")

                # Also grab any extra emails/phones/social from about page
                extra_phones = _extract_all_phones(about_soup, biz.get("phone"))
                extra_emails = _extract_all_emails(about_soup, biz.get("email"), base_domain)
                for p in extra_phones:
                    if p not in enrichment["additional_phones"]:
                        enrichment["additional_phones"].append(p)
                for e in extra_emails:
                    if e not in enrichment["additional_emails"]:
                        enrichment["additional_emails"].append(e)

                if not enrichment["social_links"]:
                    enrichment["social_links"] = _extract_social_links(about_soup, website_url)

                if contact:
                    break  # found what we need
            except (httpx.RequestError, Exception):
                continue

    # Filter out None values
    return {k: v for k, v in enrichment.items() if v is not None}


def _extract_social_links(soup: BeautifulSoup, base_url: str) -> dict[str, str]:
    """Extract social media links from page."""
    links: dict[str, str] = {}
    parsed_base = urlparse(base_url)

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        try:
            parsed = urlparse(href)
            domain = parsed.netloc.lower().removeprefix("www.")
        except Exception:
            continue

        # Skip same-domain links
        if domain == parsed_base.netloc.lower().removeprefix("www."):
            continue

        for social_domain, platform in _SOCIAL_DOMAINS.items():
            if social_domain in domain and platform not in links:
                links[platform] = href
                break

    return links


def _extract_all_phones(soup: BeautifulSoup, primary_phone: str | None) -> list[str]:
    """Extract all phone numbers from page, excluding the primary one."""
    text = soup.get_text()
    phones = set()

    for match in _PHONE_REGEX.findall(text):
        # Normalize: strip non-digits
        digits = re.sub(r"\D", "", match)
        if len(digits) == 10 or (len(digits) == 11 and digits.startswith("1")):
            phones.add(match.strip())

    # Also check tel: links
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith("tel:"):
            phone = href[4:].strip()
            if phone:
                phones.add(phone)

    # Remove primary phone
    if primary_phone:
        primary_digits = re.sub(r"\D", "", primary_phone)
        phones = {p for p in phones if re.sub(r"\D", "", p) != primary_digits}

    return list(phones)[:5]  # cap at 5


def _extract_all_emails(soup: BeautifulSoup, primary_email: str | None, base_domain: str) -> list[str]:
    """Extract all emails from page, excluding the primary one and junk domains."""
    emails = set()

    text = soup.get_text()
    for match in _EMAIL_REGEX.findall(text):
        emails.add(match.lower())

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith("mailto:"):
            email = href[7:].split("?")[0].strip().lower()
            if email:
                emails.add(email)

    # Filter junk
    filtered = []
    for e in emails:
        domain = e.split("@")[-1]
        if domain in _JUNK_EMAIL_DOMAINS:
            continue
        if e == (primary_email or "").lower():
            continue
        if not e.endswith((".png", ".jpg", ".svg", ".gif", ".css", ".js")):
            filtered.append(e)

    return filtered[:5]  # cap at 5


def _find_contact_in_html(soup: BeautifulSoup) -> dict | None:
    """Try to find an owner/manager name from HTML content."""
    text = soup.get_text(separator="\n")

    # Look for lines containing title keywords
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line) > 200:
            continue

        if _TITLE_KEYWORDS.search(line):
            # Try to extract a name from this line or nearby
            names = _NAME_PATTERN.findall(line)
            if names:
                name = names[0].strip()
                # Extract the title
                title_match = _TITLE_KEYWORDS.search(line)
                title = title_match.group(0).title() if title_match else None
                return {"name": name, "title": title}

    # Also check structured data (JSON-LD)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            data = json.loads(script.string or "")
            # Look for Person or Organization with founder/employee
            if isinstance(data, dict):
                for key in ("founder", "employee", "author", "contactPoint"):
                    person = data.get(key)
                    if isinstance(person, dict) and person.get("name"):
                        return {"name": person["name"], "title": key.title()}
                    if isinstance(person, list) and person and person[0].get("name"):
                        return {"name": person[0]["name"], "title": key.title()}
        except Exception:
            continue

    return None


def _extract_jsonld_hours(soup: BeautifulSoup) -> str | None:
    """Extract business hours from JSON-LD structured data."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                hours = data.get("openingHours")
                if hours:
                    if isinstance(hours, list):
                        return "; ".join(hours)
                    return str(hours)
        except Exception:
            continue
    return None


def _format_yelp_hours(hours_data: list) -> str:
    """Format Yelp hours data into a readable string."""
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    try:
        open_hours = hours_data[0].get("open", [])
        parts = []
        for entry in open_hours:
            day_idx = entry.get("day", 0)
            start = entry.get("start", "")
            end = entry.get("end", "")
            if start and end:
                day = days[day_idx] if day_idx < len(days) else f"Day{day_idx}"
                parts.append(f"{day} {start[:2]}:{start[2:]}-{end[:2]}:{end[2:]}")
        return "; ".join(parts) if parts else None
    except (IndexError, KeyError, TypeError):
        return None
