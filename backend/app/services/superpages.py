"""Superpages scraper — uses headless Chrome to bypass bot detection."""

import re
import logging
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"(\d{3}[\-\.]\d{3}[\-\.]\d{4})")


async def scrape_superpages(category: str, location: str, pages: int = 1) -> list[dict]:
    """Scrape Superpages using headless Chrome."""
    from agent.browser import scrape_page

    query = quote_plus(category)
    loc = quote_plus(location)
    url = f"https://www.superpages.com/search?search_terms={query}&geo_location_terms={loc}"

    results = []
    try:
        data = await scrape_page(url)
        if not data.get("success"):
            return []

        text = data.get("text", "")
        results = _parse_sp_text(text, category)
        logger.info(f"SP: found {len(results)} businesses for {category} in {location}")
    except Exception as e:
        logger.error(f"SP scrape failed: {e}")

    return results


def _parse_sp_text(text: str, category: str) -> list[dict]:
    """Parse Superpages from rendered text.

    Format is numbered listings:
      1. Business Name
      555-123-4567
      Visit Website
      Directions
      Category tags
      123 Main St, City, ST 12345
    """
    businesses = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    i = 0
    while i < len(lines):
        numbered = re.match(r"^(\d+)\.\s+(.+)$", lines[i])
        if not numbered:
            i += 1
            continue

        name = numbered.group(2).strip()
        phone = None
        city = ""
        state = ""
        address = ""

        for j in range(i + 1, min(i + 15, len(lines))):
            ln = lines[j]

            # Next numbered entry — stop
            if re.match(r"^\d+\.\s+", ln) and j > i + 1:
                break

            # Phone (format: 555-123-4567)
            if not phone:
                phone_match = _PHONE_RE.search(ln)
                if phone_match and len(ln) < 20:
                    phone = phone_match.group(1)
                    continue

            # Address with state + zip
            state_match = re.search(r",\s*([A-Z]{2})\s+\d{5}", ln)
            if state_match and len(ln) < 100:
                address = ln
                state = state_match.group(1)
                parts = ln.split(",")
                if len(parts) >= 2:
                    city = parts[-2].strip()

        if name and (phone or city):
            businesses.append({
                "business_name": name,
                "phone": phone,
                "website_url": None,
                "city": city,
                "state": state,
                "category": category,
                "source": "superpages",
                "raw_data": {"address": address},
            })

        i += 1

    return businesses
