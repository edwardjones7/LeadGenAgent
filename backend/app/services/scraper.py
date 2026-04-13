"""Yellow Pages scraper — uses headless Chrome to bypass bot detection."""

import re
import logging
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"(\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4})")
_ADDR_RE = re.compile(r",\s*([^,]+),\s*([A-Z]{2})\s*\d*$")


async def scrape_yellowpages(category: str, location: str, pages: int = 1) -> list[dict]:
    """Scrape Yellow Pages using headless Chrome."""
    from agent.browser import scrape_page

    loc_slug = quote_plus(location.lower().replace(", ", "-").replace(" ", "-"))
    cat_slug = quote_plus(category.lower().replace(" ", "-"))
    url = f"https://www.yellowpages.com/{loc_slug}/{cat_slug}"

    results = []
    try:
        data = await scrape_page(url)
        if not data.get("success"):
            return []

        text = data.get("text", "")
        results = _parse_yp_text(text, category)
        logger.info(f"YP: found {len(results)} businesses for {category} in {location}")
    except Exception as e:
        logger.error(f"YP scrape failed: {e}")

    return results


def _parse_yp_text(text: str, category: str) -> list[dict]:
    """Parse structured text from Yellow Pages rendered page."""
    businesses = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]

        # Look for numbered listings: "1. Business Name" or just business-like entries
        numbered = re.match(r"^(\d+)\.\s+(.+)$", line)
        if not numbered:
            i += 1
            continue

        name = numbered.group(2).strip()
        phone = None
        website = None
        address = ""
        city = ""
        state = ""

        # Scan next few lines for phone, address
        for j in range(i + 1, min(i + 12, len(lines))):
            ln = lines[j]

            # Phone
            if not phone:
                phone_match = _PHONE_RE.search(ln)
                if phone_match and len(ln) < 30:
                    phone = phone_match.group(1)
                    continue

            # Address — "City, ST 12345" format
            state_zip = re.match(r"^([A-Za-z\s]+),\s*([A-Z]{2})\s+\d{5}", ln)
            if state_zip and len(ln) < 60 and not city:
                city = state_zip.group(1).strip()
                state = state_zip.group(2).strip()
                address = ln

            # "Visit Website" link indicator
            if "Visit Website" in ln or "Website" == ln.strip():
                website = "unknown"  # We know they have one but don't have the URL from text

            # Stop at next numbered entry
            if re.match(r"^\d+\.\s+", ln) and j > i + 1:
                break

        if name and (phone or city):
            businesses.append({
                "business_name": name,
                "phone": phone,
                "website_url": None,  # YP text doesn't expose actual URLs
                "city": city,
                "state": state,
                "category": category,
                "source": "yellowpages",
                "raw_data": {"address": address},
            })

        i += 1

    return businesses
