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
CONTACT_PATHS = ["/contact", "/contact-us", "/contact.html", "/about", "/about-us"]
PRIORITY_PREFIXES = ["info", "contact", "hello", "support", "admin"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


async def extract_email(url: str, homepage_html: str, client: httpx.AsyncClient) -> str | None:
    """Extract the best contact email from a business website."""
    base_domain = urlparse(url).netloc.lower().removeprefix("www.")

    # 1. Try homepage HTML first (already fetched during evaluation)
    emails = _extract_from_html(homepage_html, base_domain)
    if emails:
        return _pick_best(emails, base_domain)

    # 2. Try contact/about pages
    for path in CONTACT_PATHS:
        contact_url = urljoin(url, path)
        try:
            resp = await client.get(contact_url, timeout=8.0, follow_redirects=True)
            if resp.status_code == 200:
                emails = _extract_from_html(resp.text, base_domain)
                if emails:
                    return _pick_best(emails, base_domain)
        except httpx.RequestError:
            continue

    return None


def _extract_from_html(html: str, base_domain: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")

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
