import asyncio
import random
import re
import httpx
from bs4 import BeautifulSoup

YP_BASE = "https://www.yellowpages.com/search"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


async def scrape_yellowpages(category: str, location: str, pages: int = 2) -> list[dict]:
    """Scrape Yellow Pages for businesses in a given category and location."""
    results = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
        for page in range(1, pages + 1):
            try:
                resp = await client.get(
                    YP_BASE,
                    params={
                        "search_terms": category,
                        "geo_location_terms": location,
                        "page": page,
                    },
                )
                if resp.status_code != 200:
                    break

                businesses = _parse_listings(resp.text, category)
                if not businesses:
                    break

                results.extend(businesses)

                if page < pages:
                    await asyncio.sleep(random.uniform(1.5, 2.5))

            except httpx.RequestError:
                break

    return results


def _parse_listings(html: str, category: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    listings = soup.select("div.result")
    businesses = []

    for listing in listings:
        name_tag = listing.select_one(".business-name a")
        if not name_tag:
            continue

        name = name_tag.get_text(strip=True)

        phone_tag = listing.select_one(".phones.phone.primary")
        phone = phone_tag.get_text(strip=True) if phone_tag else None

        website_tag = listing.select_one("a.track-visit-website")
        website = website_tag.get("href") if website_tag else None
        if website and website.startswith("/"):
            website = None  # relative links are YP internal, not real websites

        addr_tag = listing.select_one(".adr")
        address_text = addr_tag.get_text(separator=" ", strip=True) if addr_tag else ""

        city, state = _parse_city_state(address_text)

        businesses.append({
            "business_name": name,
            "phone": phone,
            "website_url": website,
            "city": city,
            "state": state,
            "category": category,
            "source": "yellowpages",
            "raw_data": {"address": address_text},
        })

    return businesses


def _parse_city_state(address: str) -> tuple[str, str]:
    """Extract city and state from an address string like '123 Main St, Camden, NJ 08102'."""
    match = re.search(r",\s*([^,]+),\s*([A-Z]{2})\s*\d*$", address)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", ""
