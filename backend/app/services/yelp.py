import re
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings

YELP_BASE = "https://api.yelp.com/v3"

_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


async def search_businesses(category: str, location: str) -> list[dict]:
    """Fetch up to 150 businesses from Yelp for a given category and location."""
    results = []
    headers = {"Authorization": f"Bearer {settings.yelp_api_key}"}
    async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
        for offset in range(0, 1000, 50):
            try:
                resp = await client.get(
                    f"{YELP_BASE}/businesses/search",
                    params={
                        "term": category,
                        "location": location,
                        "limit": 50,
                        "offset": offset,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                businesses = data.get("businesses", [])
                if not businesses:
                    break
                results.extend(businesses)
                if offset + 50 >= data.get("total", 0):
                    break
            except httpx.HTTPStatusError:
                break  # stop pagination on any HTTP error (400 = past offset limit, 429 = rate limit)
    return results


def normalize(business: dict, category: str) -> dict:
    """Normalize a Yelp business record to our internal format.

    Note: Yelp search API returns the Yelp listing URL in 'url', NOT the
    business's own website. Website discovery is handled by the Yellow Pages
    scraper or the evaluator attempting a Google-like lookup.
    """
    location = business.get("location", {})
    return {
        "business_name": business.get("name", ""),
        "city": location.get("city", ""),
        "state": location.get("state", ""),
        "phone": business.get("display_phone") or None,
        "website_url": None,  # populated later by enrichment or cross-reference
        "category": category,
        "source": "yelp",
        "raw_data": business,
        "_yelp_id": business.get("id"),
    }


async def get_website_url(yelp_id: str) -> str | None:
    """Scrape the Yelp listing page to extract the business's actual website URL.

    Yelp redirects outbound website clicks through /biz_redir links. We look for
    those redirect links or a direct "Business website" href on the page.
    """
    listing_url = f"https://www.yelp.com/biz/{yelp_id}"
    try:
        async with httpx.AsyncClient(headers=_SCRAPE_HEADERS, timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(listing_url)
            if resp.status_code != 200:
                return None
            html = resp.text[:100_000]  # cap to avoid huge pages
    except (httpx.RequestError, httpx.HTTPStatusError):
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Method 1: Look for /biz_redir redirect links (Yelp wraps outbound website clicks)
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/biz_redir" in href and "url=" in href:
            # Extract the actual URL from the redirect parameter
            match = re.search(r"url=([^&]+)", href)
            if match:
                website = unquote(match.group(1))
                if _is_valid_business_url(website):
                    return website

    # Method 2: Look for links with "business website" text
    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True).lower()
        if "business website" in text or "company website" in text:
            href = a_tag["href"]
            if href.startswith("http") and _is_valid_business_url(href):
                return href

    # Method 3: Check JSON-LD structured data
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            data = json.loads(script.string or "")
            url = data.get("url") or ""
            if url and "yelp.com" not in url and _is_valid_business_url(url):
                return url
        except (json.JSONDecodeError, AttributeError):
            continue

    return None


def _is_valid_business_url(url: str) -> bool:
    """Filter out Yelp/social media URLs — we only want actual business websites."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
    except Exception:
        return False
    skip_domains = {
        "yelp.com", "facebook.com", "instagram.com", "twitter.com",
        "x.com", "linkedin.com", "youtube.com", "tiktok.com",
    }
    return bool(domain) and domain not in skip_domains
