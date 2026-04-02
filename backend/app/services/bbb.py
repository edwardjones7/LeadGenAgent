import asyncio
import json
import random
import re
import httpx
from bs4 import BeautifulSoup

BBB_BASE = "https://www.bbb.org/search"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


async def scrape_bbb(category: str, location: str, pages: int = 3) -> list[dict]:
    """Scrape Better Business Bureau for businesses in a given category and location."""
    results = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
        for page in range(1, pages + 1):
            try:
                resp = await client.get(
                    BBB_BASE,
                    params={"find_text": category, "find_loc": location, "page": page},
                )
                if resp.status_code != 200:
                    break

                businesses = _parse_bbb(resp.text, category)
                if not businesses:
                    break

                results.extend(businesses)

                if page < pages:
                    await asyncio.sleep(random.uniform(1.5, 2.5))

            except httpx.RequestError:
                break

    return results


def _parse_bbb(html: str, category: str) -> list[dict]:
    # BBB is a Next.js app — try __NEXT_DATA__ JSON first (most reliable)
    next_data_match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if next_data_match:
        try:
            data = json.loads(next_data_match.group(1))
            businesses = (
                data.get("props", {})
                    .get("pageProps", {})
                    .get("searchResults", {})
                    .get("businesses", [])
            )
            if businesses:
                return [_normalize_bbb_json(b, category) for b in businesses if b]
        except (json.JSONDecodeError, AttributeError, KeyError):
            pass

    # Fallback: HTML parsing for any layout changes
    soup = BeautifulSoup(html, "lxml")
    listings = soup.select(
        "div.result-details, "
        "div[class*='SearchResults__result'], "
        "div[class*='ResultCard']"
    )
    businesses = []

    for listing in listings:
        name_tag = listing.select_one(
            "a[class*='business-name'], h3 a, .result-title a, a[class*='BusinessName']"
        )
        if not name_tag:
            continue
        name = name_tag.get_text(strip=True)

        phone = None
        phone_tag = listing.select_one("a[href^='tel:'], [class*='phone'], [class*='Phone']")
        if phone_tag:
            href = phone_tag.get("href", "")
            phone = href[4:].strip() if href.startswith("tel:") else phone_tag.get_text(strip=True)

        website = None
        for a in listing.select("a[href^='http']"):
            href = a.get("href", "")
            if "bbb.org" not in href:
                website = href
                break

        addr_tag = listing.select_one("address, [class*='address'], [class*='Address']")
        address_text = addr_tag.get_text(separator=" ", strip=True) if addr_tag else ""
        city, state = _parse_city_state(address_text)

        businesses.append({
            "business_name": name,
            "phone": phone,
            "website_url": website,
            "city": city,
            "state": state,
            "category": category,
            "source": "bbb",
            "raw_data": {"address": address_text},
        })

    return businesses


def _normalize_bbb_json(b: dict, category: str) -> dict:
    """Normalize a BBB JSON record from __NEXT_DATA__."""
    address = b.get("primaryAddress") or b.get("address") or {}
    city = address.get("city") or address.get("addressLocality") or ""
    state = address.get("stateProvince") or address.get("addressRegion") or ""

    phone = b.get("phone") or b.get("primaryPhone") or b.get("telephone")
    website = b.get("website") or b.get("websiteURL") or b.get("url")
    if website and not website.startswith("http"):
        website = None

    return {
        "business_name": b.get("businessName") or b.get("name") or "",
        "phone": phone,
        "website_url": website,
        "city": city,
        "state": state,
        "category": category,
        "source": "bbb",
        "raw_data": b,
    }


def _parse_city_state(address: str) -> tuple[str, str]:
    match = re.search(r",\s*([^,]+),\s*([A-Z]{2})\s*\d*$", address)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", ""
