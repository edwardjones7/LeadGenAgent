import httpx
from app.config import settings

YELP_BASE = "https://api.yelp.com/v3"


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
        "website_url": None,  # populated later by Yellow Pages cross-reference
        "category": category,
        "source": "yelp",
        "raw_data": business,
        "_yelp_id": business.get("id"),
    }
