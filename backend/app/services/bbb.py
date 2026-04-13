"""BBB scraper — uses headless Chrome to bypass bot detection."""

import re
import logging
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"(\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4})")


async def scrape_bbb(category: str, location: str, pages: int = 1) -> list[dict]:
    """Scrape BBB using headless Chrome."""
    from agent.browser import scrape_page

    query = quote_plus(category)
    loc = quote_plus(location)
    url = f"https://www.bbb.org/search?find_text={query}&find_loc={loc}"

    results = []
    try:
        data = await scrape_page(url)
        if not data.get("success"):
            return []

        text = data.get("text", "")
        results = _parse_bbb_text(text, category)
        logger.info(f"BBB: found {len(results)} businesses for {category} in {location}")
    except Exception as e:
        logger.error(f"BBB scrape failed: {e}")

    return results


def _parse_bbb_text(text: str, category: str) -> list[dict]:
    """Parse BBB search results from rendered page text.

    BBB results follow a pattern like:
      Business Name
      BBB Rating: A+
      Phone: (555) 123-4567
      City, ST 12345
    """
    businesses = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    i = 0
    while i < len(lines):
        # BBB results often have "BBB Rating:" nearby
        # Look for phone numbers and work backwards to find the business name
        line = lines[i]

        # Detect a BBB rating line — the business name is typically 1-3 lines above
        if "BBB Rating:" in line or "Not BBB Accredited" in line:
            name = None
            phone = None
            city = ""
            state = ""

            # Look backwards for the business name
            # Pattern: Name is 2-3 lines before "BBB Rating:", category line is in between
            # Skip: category-like lines, junk, icons, short strings
            _SKIP = {"Phone:", "Website", "Get a Quote", "Directions", "Ad",
                      "advertisement:", "Why are there ads on BBB.org?", "�"}
            candidates = []
            for j in range(i - 1, max(i - 5, -1), -1):
                candidate = lines[j]
                if (len(candidate) > 3
                    and not candidate.startswith("BBB")
                    and not _PHONE_RE.search(candidate)
                    and "Rating" not in candidate
                    and "Accredited" not in candidate
                    and candidate not in _SKIP
                    and not re.match(r"^\d+\.\s*$", candidate)
                    and not re.search(r"[A-Z]{2}\s+\d{5}", candidate)  # skip address lines
                    and not re.match(r"^\d+\s+\w", candidate)):  # skip "123 Main St"
                    candidates.append(candidate)

            # The actual business name is usually the one furthest back (before category)
            if len(candidates) >= 2:
                name = candidates[-1]  # furthest back = business name
            elif candidates:
                name = candidates[0]

            # Look forward for phone and address
            for j in range(i + 1, min(i + 10, len(lines))):
                ln = lines[j]

                if not phone:
                    phone_match = _PHONE_RE.search(ln)
                    if phone_match:
                        phone = phone_match.group(1)

                # Address with state + zip
                state_match = re.search(r",\s*([A-Z]{2})\s+\d{5}", ln)
                if state_match and len(ln) < 80:
                    state = state_match.group(1)
                    parts = ln.split(",")
                    if len(parts) >= 2:
                        city = parts[-2].strip()

                # Stop at next BBB Rating
                if "BBB Rating:" in ln and j > i + 1:
                    break

            if name and len(name) < 80:
                businesses.append({
                    "business_name": name,
                    "phone": phone,
                    "website_url": None,
                    "city": city,
                    "state": state,
                    "category": category,
                    "source": "bbb",
                    "raw_data": {},
                })

        i += 1

    return businesses
