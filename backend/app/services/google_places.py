"""Google Places API (v1) — Text Search.

Docs: https://developers.google.com/maps/documentation/places/web-service/text-search

Unlike Yelp, Text Search returns the business's actual website URL directly in
the response when we request the right field mask, so no enrichment pass is
needed for google-sourced leads.
"""

import httpx

from app.config import settings

PLACES_BASE = "https://places.googleapis.com/v1"

# Field mask controls which fields the API returns — and the billing tier.
# We only ask for what we use.
_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.addressComponents",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.businessStatus",
    "places.types",
    "nextPageToken",
])


async def search_businesses(category: str, location: str) -> list[dict]:
    """Return up to ~60 businesses for a category + location (3 paginated pages of 20)."""
    api_key = getattr(settings, "google_places_api_key", None)
    if not api_key:
        return []

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": _FIELD_MASK,
    }
    body = {
        "textQuery": f"{category} in {location}",
        "pageSize": 20,
    }

    results: list[dict] = []
    next_token: str | None = None

    async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
        for _ in range(3):  # up to 3 pages × 20 = 60 results
            payload = dict(body)
            if next_token:
                payload["pageToken"] = next_token
            try:
                resp = await client.post(f"{PLACES_BASE}/places:searchText", json=payload)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError):
                break

            places = data.get("places", []) or []
            results.extend(places)

            next_token = data.get("nextPageToken")
            if not next_token or not places:
                break

    return results


def _extract_city_state(place: dict) -> tuple[str, str]:
    """Pull the locality (city) and administrative_area_level_1 (state) from address components."""
    city = ""
    state = ""
    for comp in place.get("addressComponents", []) or []:
        types = comp.get("types", []) or []
        if "locality" in types and not city:
            city = comp.get("shortText") or comp.get("longText") or ""
        elif "postal_town" in types and not city:  # fallback for some regions
            city = comp.get("shortText") or comp.get("longText") or ""
        elif "administrative_area_level_1" in types and not state:
            state = comp.get("shortText") or comp.get("longText") or ""
    # Fallback — parse from formattedAddress "..., City, ST 12345, USA"
    if (not city or not state) and place.get("formattedAddress"):
        parts = [p.strip() for p in place["formattedAddress"].split(",")]
        if len(parts) >= 3:
            if not city:
                city = parts[-3]
            if not state:
                # second-to-last often "ST 12345"
                tail = parts[-2].split()
                if tail:
                    state = tail[0]
    return city, state


def normalize(place: dict, category: str) -> dict:
    """Normalize a Google Places record to our internal format."""
    name = (place.get("displayName") or {}).get("text", "") or ""
    city, state = _extract_city_state(place)
    return {
        "business_name": name,
        "city": city,
        "state": state,
        "phone": place.get("nationalPhoneNumber") or None,
        "website_url": place.get("websiteUri") or None,
        "category": category,
        "source": "google",
        "raw_data": place,
    }
