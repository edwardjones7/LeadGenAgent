import uuid
from datetime import datetime, timezone

import httpx

from app.database import get_db
from app.services import yelp, scraper, bbb, manta, superpages, evaluator, email_extractor

EVAL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Hard cap on new leads evaluated per search run — keeps memory bounded
MAX_LEADS_PER_RUN = 40


async def run_search(location: str, categories: list[str]) -> dict:
    """Full pipeline: fetch → dedupe → score → save → return results."""
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    db = get_db()

    raw_businesses: list[dict] = []

    # 1a. Yelp — sequential per category (each call loops up to 20 paginated requests)
    for i, cat in enumerate(categories):
        try:
            result = await yelp.search_businesses(cat, location)
            for biz in result:
                raw_businesses.append(yelp.normalize(biz, cat))
        except Exception:
            continue

    # 1b. Scrapers — 1 page per source to reduce HTML volume
    for cat in categories:
        try:
            raw_businesses.extend(await scraper.scrape_yellowpages(cat, location, pages=1))
        except Exception:
            pass

    for cat in categories:
        try:
            raw_businesses.extend(await bbb.scrape_bbb(cat, location, pages=1))
        except Exception:
            pass

    for cat in categories:
        try:
            raw_businesses.extend(await manta.scrape_manta(cat, location, pages=1))
        except Exception:
            pass

    for cat in categories:
        try:
            raw_businesses.extend(await superpages.scrape_superpages(cat, location, pages=1))
        except Exception:
            pass

    # 2. Deduplicate against existing DB records and within this batch
    # Per-item DB queries instead of loading full table into memory sets
    new_businesses: list[dict] = []
    dupes_skipped = 0
    seen_in_batch: dict[tuple[str, str], int] = {}

    for biz in raw_businesses:
        phone = biz.get("phone")
        name_city = (biz["business_name"].lower(), biz["city"].lower())

        # Within-batch dedup (fast, no DB round trip)
        if name_city in seen_in_batch:
            existing_idx = seen_in_batch[name_city]
            if biz.get("website_url") and not new_businesses[existing_idx].get("website_url"):
                new_businesses[existing_idx]["website_url"] = biz["website_url"]
            dupes_skipped += 1
            continue

        # DB dedup — targeted indexed queries, no full table scan
        if await _is_duplicate(db, phone, biz["business_name"], biz["city"]):
            dupes_skipped += 1
            continue

        seen_in_batch[name_city] = len(new_businesses)
        new_businesses.append(biz)

    # 3. Evaluate and save — sequential, one lead at a time
    # Each lead's HTML and parse tree are GC'd before the next one starts
    new_leads_saved: list[dict] = []

    async with httpx.AsyncClient(headers=EVAL_HEADERS, timeout=12.0, follow_redirects=True) as client:
        for biz in new_businesses:
            if len(new_leads_saved) >= MAX_LEADS_PER_RUN:
                break
            try:
                lead = await _score_lead(biz, client)
            except Exception:
                continue
            try:
                db.table("leads").insert(lead).execute()
                new_leads_saved.append(lead)
            except Exception:
                continue

    # 4. Log search run
    finished_at = datetime.now(timezone.utc)
    try:
        db.table("search_runs").insert({
            "id": run_id,
            "location": location,
            "categories": categories,
            "total_found": len(raw_businesses),
            "new_leads": len(new_leads_saved),
            "dupes_skipped": dupes_skipped,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        }).execute()
    except Exception:
        pass

    return {
        "run_id": run_id,
        "new_leads": len(new_leads_saved),
        "dupes_skipped": dupes_skipped,
        "leads": new_leads_saved,
    }


async def _is_duplicate(db, phone: str | None, name: str, city: str) -> bool:
    """Check if a lead already exists — uses indexed queries, no full table scan."""
    if phone:
        try:
            r = db.table("leads").select("id").eq("phone", phone).limit(1).execute()
            if r.data:
                return True
        except Exception:
            pass
    try:
        r = (
            db.table("leads")
            .select("id")
            .ilike("business_name", name)
            .ilike("city", city)
            .limit(1)
            .execute()
        )
        if r.data:
            return True
    except Exception:
        pass
    return False


async def _score_lead(biz: dict, client: httpx.AsyncClient) -> dict:
    website_url = biz.get("website_url")

    if not website_url:
        score_data = {"score": 10, "score_reason": "No website found", "homepage_html": ""}
        email = None
    else:
        # evaluate() fetches the page (50KB cap) and returns homepage_html
        # so we don't fetch the URL a second time
        score_data = await evaluator.evaluate(website_url, client)
        homepage_html = score_data.pop("homepage_html", "")

        # Only extract emails for high-scoring leads (bad website = hot prospect)
        email = None
        if score_data["score"] >= 5:
            email = await email_extractor.extract_email(website_url, homepage_html, client)

    return {
        "business_name": biz["business_name"],
        "city": biz["city"],
        "state": biz["state"],
        "phone": biz.get("phone"),
        "email": email,
        "website_url": website_url,
        "score": score_data["score"],
        "score_reason": score_data["score_reason"],
        "status": "New",
        "category": biz.get("category"),
        "source": biz.get("source"),
        "raw_data": biz.get("raw_data"),
    }
