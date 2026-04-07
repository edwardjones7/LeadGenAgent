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

    # 2b. Enrich Yelp leads that are missing website URLs
    yelp_needs_website = [
        biz for biz in new_businesses
        if biz.get("source") == "yelp" and not biz.get("website_url") and biz.get("raw_data", {}).get("id")
    ]
    if yelp_needs_website:
        sem = asyncio.Semaphore(5)

        async def _enrich(biz: dict):
            async with sem:
                url = await yelp.get_website_url(biz["raw_data"]["id"])
                if url:
                    biz["website_url"] = url

        await asyncio.gather(*[_enrich(b) for b in yelp_needs_website], return_exceptions=True)

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


async def run_search_stream(location: str, categories: list[str]):
    """Streaming variant of run_search — yields log events, then the final result."""
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    db = get_db()

    def _evt(type_: str, stage: str, message: str, **extra):
        d = {"type": type_, "stage": stage, "message": message}
        d.update(extra)
        return d

    raw_businesses: list[dict] = []

    # 1a. Yelp
    for cat in categories:
        yield _evt("log", "yelp", f"Searching Yelp for {cat}...")
        try:
            result = await yelp.search_businesses(cat, location)
            count = len(result)
            for biz in result:
                raw_businesses.append(yelp.normalize(biz, cat))
            yield _evt("log", "yelp", f"Found {count} from Yelp ({cat})")
        except Exception:
            yield _evt("log", "yelp", f"Yelp search failed for {cat}")

    # 1b. Scrapers
    scraper_sources = [
        ("yellowpages", "Yellow Pages", lambda cat: scraper.scrape_yellowpages(cat, location, pages=1)),
        ("bbb", "BBB", lambda cat: bbb.scrape_bbb(cat, location, pages=1)),
        ("manta", "Manta", lambda cat: manta.scrape_manta(cat, location, pages=1)),
        ("superpages", "Superpages", lambda cat: superpages.scrape_superpages(cat, location, pages=1)),
    ]

    for source_id, source_name, scrape_fn in scraper_sources:
        for cat in categories:
            yield _evt("log", source_id, f"Scraping {source_name} for {cat}...")
            try:
                results = await scrape_fn(cat)
                raw_businesses.extend(results)
                yield _evt("log", source_id, f"Found {len(results)} from {source_name} ({cat})")
            except Exception:
                yield _evt("log", source_id, f"{source_name} failed for {cat}")

    yield _evt("log", "collect", f"Collected {len(raw_businesses)} raw businesses total")

    # 2. Dedup
    yield _evt("log", "dedup", "Deduplicating against database...")
    new_businesses: list[dict] = []
    dupes_skipped = 0
    seen_in_batch: dict[tuple[str, str], int] = {}

    for biz in raw_businesses:
        phone = biz.get("phone")
        name_city = (biz["business_name"].lower(), biz["city"].lower())
        if name_city in seen_in_batch:
            existing_idx = seen_in_batch[name_city]
            if biz.get("website_url") and not new_businesses[existing_idx].get("website_url"):
                new_businesses[existing_idx]["website_url"] = biz["website_url"]
            dupes_skipped += 1
            continue
        if await _is_duplicate(db, phone, biz["business_name"], biz["city"]):
            dupes_skipped += 1
            continue
        seen_in_batch[name_city] = len(new_businesses)
        new_businesses.append(biz)

    yield _evt("log", "dedup", f"Deduplication complete — {dupes_skipped} duplicates removed, {len(new_businesses)} new")

    # 2b. Enrich
    yelp_needs_website = [
        biz for biz in new_businesses
        if biz.get("source") == "yelp" and not biz.get("website_url") and biz.get("raw_data", {}).get("id")
    ]
    if yelp_needs_website:
        yield _evt("log", "enrich", f"Enriching {len(yelp_needs_website)} Yelp leads with website URLs...")
        sem = asyncio.Semaphore(5)

        async def _enrich(biz: dict):
            async with sem:
                url = await yelp.get_website_url(biz["raw_data"]["id"])
                if url:
                    biz["website_url"] = url

        await asyncio.gather(*[_enrich(b) for b in yelp_needs_website], return_exceptions=True)
        enriched = sum(1 for b in yelp_needs_website if b.get("website_url"))
        yield _evt("log", "enrich", f"Enriched {enriched}/{len(yelp_needs_website)} with website URLs")

    # 3. Score and save
    to_score = min(len(new_businesses), MAX_LEADS_PER_RUN)
    yield _evt("log", "score", f"Scoring {to_score} leads...")
    new_leads_saved: list[dict] = []

    async with httpx.AsyncClient(headers=EVAL_HEADERS, timeout=12.0, follow_redirects=True) as client:
        for i, biz in enumerate(new_businesses):
            if len(new_leads_saved) >= MAX_LEADS_PER_RUN:
                break
            yield _evt("progress", "score",
                        f"Scoring {i + 1}/{to_score}: {biz['business_name']}",
                        progress={"current": i + 1, "total": to_score})
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

    yield _evt("log", "done", f"Search complete — {len(new_leads_saved)} new leads saved")

    yield {
        "type": "result",
        "data": {
            "run_id": run_id,
            "new_leads": len(new_leads_saved),
            "dupes_skipped": dupes_skipped,
            "leads": new_leads_saved,
        },
    }


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
