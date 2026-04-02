import asyncio
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


async def run_search(location: str, categories: list[str]) -> dict:
    """Full pipeline: fetch → dedupe → score → save → return results."""
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    db = get_db()

    raw_businesses: list[dict] = []

    # 1a. Yelp — concurrent across categories
    yelp_tasks = [yelp.search_businesses(cat, location) for cat in categories]
    yelp_results_nested = await asyncio.gather(*yelp_tasks, return_exceptions=True)
    for i, result in enumerate(yelp_results_nested):
        if isinstance(result, Exception):
            continue
        for biz in result:
            raw_businesses.append(yelp.normalize(biz, categories[i]))

    # 1b. Scrapers — sequential per source to be polite
    for cat in categories:
        try:
            raw_businesses.extend(await scraper.scrape_yellowpages(cat, location, pages=5))
        except Exception:
            pass

    for cat in categories:
        try:
            raw_businesses.extend(await bbb.scrape_bbb(cat, location, pages=3))
        except Exception:
            pass

    for cat in categories:
        try:
            raw_businesses.extend(await manta.scrape_manta(cat, location, pages=3))
        except Exception:
            pass

    for cat in categories:
        try:
            raw_businesses.extend(await superpages.scrape_superpages(cat, location, pages=3))
        except Exception:
            pass

    # 2. Deduplicate against existing DB records
    existing_phones: set[str] = set()
    existing_name_city: set[tuple[str, str]] = set()

    try:
        phone_rows = db.table("leads").select("phone").not_.is_("phone", "null").execute()
        existing_phones = {r["phone"] for r in phone_rows.data if r["phone"]}

        nc_rows = db.table("leads").select("business_name,city").execute()
        existing_name_city = {
            (r["business_name"].lower(), r["city"].lower())
            for r in nc_rows.data
        }
    except Exception:
        pass

    new_businesses: list[dict] = []
    dupes_skipped = 0
    # Map name_city -> index in new_businesses so we can merge website_url across sources
    seen_in_batch: dict[tuple[str, str], int] = {}

    for biz in raw_businesses:
        phone = biz.get("phone")
        name_city = (biz["business_name"].lower(), biz["city"].lower())

        if phone and phone in existing_phones:
            dupes_skipped += 1
            continue
        if name_city in existing_name_city:
            dupes_skipped += 1
            continue

        if name_city in seen_in_batch:
            # Merge: if this record has a website and the existing one doesn't, upgrade it
            existing_idx = seen_in_batch[name_city]
            if biz.get("website_url") and not new_businesses[existing_idx].get("website_url"):
                new_businesses[existing_idx]["website_url"] = biz["website_url"]
            dupes_skipped += 1
            continue

        seen_in_batch[name_city] = len(new_businesses)
        if phone:
            existing_phones.add(phone)
        new_businesses.append(biz)

    # 3. Evaluate websites and extract emails concurrently (semaphore=10)
    semaphore = asyncio.Semaphore(10)
    scored_leads: list[dict] = []

    async with httpx.AsyncClient(headers=EVAL_HEADERS, timeout=12.0, follow_redirects=True) as client:
        tasks = [_score_lead(biz, client, semaphore) for biz in new_businesses]
        scored_leads = await asyncio.gather(*tasks, return_exceptions=True)

    scored_leads = [l for l in scored_leads if not isinstance(l, Exception)]

    # 4. Insert into Supabase
    if scored_leads:
        try:
            db.table("leads").insert(scored_leads).execute()
        except Exception:
            pass

    # 5. Log search run
    finished_at = datetime.now(timezone.utc)
    try:
        db.table("search_runs").insert({
            "id": run_id,
            "location": location,
            "categories": categories,
            "total_found": len(raw_businesses),
            "new_leads": len(scored_leads),
            "dupes_skipped": dupes_skipped,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        }).execute()
    except Exception:
        pass

    return {
        "run_id": run_id,
        "new_leads": len(scored_leads),
        "dupes_skipped": dupes_skipped,
        "leads": scored_leads,
    }


async def _score_lead(biz: dict, client: httpx.AsyncClient, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        website_url = biz.get("website_url")

        if not website_url:
            score_data = {"score": 10, "score_reason": "No website found"}
            email = None
            homepage_html = ""
        else:
            score_data = await evaluator.evaluate(website_url, client)
            try:
                resp = await client.get(website_url, timeout=10.0, follow_redirects=True)
                homepage_html = resp.text if resp.status_code == 200 else ""
            except Exception:
                homepage_html = ""
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
