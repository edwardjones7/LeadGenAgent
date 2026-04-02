import asyncio
import random
import re
import httpx
from bs4 import BeautifulSoup

MANTA_BASE = "https://www.manta.com/search"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


async def scrape_manta(category: str, location: str, pages: int = 3) -> list[dict]:
    """Scrape Manta business directory for a given category and location."""
    results = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
        for page in range(1, pages + 1):
            try:
                resp = await client.get(
                    MANTA_BASE,
                    params={"search": category, "location": location, "pg": page},
                )
                if resp.status_code != 200:
                    break

                businesses = _parse_manta(resp.text, category)
                if not businesses:
                    break

                results.extend(businesses)

                if page < pages:
                    await asyncio.sleep(random.uniform(1.5, 2.5))

            except httpx.RequestError:
                break

    return results


def _parse_manta(html: str, category: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    listings = soup.select(
        "article.listing-result, "
        "div.listing-result, "
        "div.search-result-item, "
        "div[class*='CompanyCard']"
    )
    businesses = []

    for listing in listings:
        name_tag = listing.select_one(
            "h2 a, h3 a, .company-name a, a.company-name, [class*='company-name']"
        )
        if not name_tag:
            continue
        name = name_tag.get_text(strip=True)

        phone = None
        phone_tag = listing.select_one(
            "a[href^='tel:'], .phone, .listing-phone, [class*='phone']"
        )
        if phone_tag:
            href = phone_tag.get("href", "")
            phone = href[4:].strip() if href.startswith("tel:") else phone_tag.get_text(strip=True)

        website = None
        for a in listing.select("a[rel~='nofollow'][href^='http'], a.website-link"):
            href = a.get("href", "")
            if href and "manta.com" not in href:
                website = href
                break

        addr_tag = listing.select_one("address, .listing-address, .address, [class*='address']")
        address_text = addr_tag.get_text(separator=" ", strip=True) if addr_tag else ""
        city, state = _parse_city_state(address_text)

        businesses.append({
            "business_name": name,
            "phone": phone,
            "website_url": website,
            "city": city,
            "state": state,
            "category": category,
            "source": "manta",
            "raw_data": {"address": address_text},
        })

    return businesses


def _parse_city_state(address: str) -> tuple[str, str]:
    match = re.search(r",\s*([^,]+),\s*([A-Z]{2})\s*\d*$", address)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", ""
