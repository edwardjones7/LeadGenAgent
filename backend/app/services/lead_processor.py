import asyncio
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlparse, quote_plus

import httpx
from bs4 import BeautifulSoup

from app.database import get_db
from app.services import yelp, google_places, scraper, superpages, evaluator, email_extractor, deep_researcher

EVAL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Hard cap on new leads evaluated per search run — keeps memory bounded
MAX_LEADS_PER_RUN = 40

# National chains / franchises — Elenos can't sell web work to corporate HQ,
# so drop these at ingest. Matched as substring against lowercased business_name.
CHAIN_BLACKLIST = {
    "starbucks", "dunkin", "dunkin'", "mcdonald", "burger king", "wendy's",
    "subway", "taco bell", "kfc", "chick-fil-a", "chipotle", "panera",
    "domino's", "pizza hut", "papa john's", "little caesars", "jimmy john",
    "five guys", "shake shack", "in-n-out", "whataburger", "arby's",
    "sonic drive-in", "dairy queen", "cold stone", "baskin-robbins",
    "tim hortons", "jamba juice", "smoothie king", "auntie anne",
    "cinnabon", "pretzelmaker", "panda express", "qdoba", "moe's southwest",
    "popeyes", "raising cane", "zaxby", "bojangles", "culver",
    "applebee", "olive garden", "red lobster", "outback steakhouse",
    "buffalo wild wings", "ihop", "denny's", "cracker barrel", "tgi friday",
    "chili's", "texas roadhouse", "longhorn steakhouse", "ruby tuesday",
    "cheesecake factory", "p.f. chang", "red robin", "bonefish grill",
    "walmart", "target", "costco", "sam's club", "bj's wholesale",
    "home depot", "lowe's", "menard", "ace hardware", "true value",
    "cvs", "walgreens", "rite aid", "duane reade",
    "7-eleven", "wawa", "sheetz", "circle k", "quiktrip", "race trac",
    "shell", "exxon", "mobil", "chevron", "bp ", "sunoco", "citgo",
    "marathon", "speedway", "valero", "76 ", "arco",
    "fedex", "ups store", "usps",
    "bank of america", "wells fargo", "chase", "citibank", "pnc bank",
    "us bank", "truist", "td bank", "capital one",
    "at&t", "verizon", "t-mobile", "sprint", "xfinity", "comcast",
    "h&r block", "jackson hewitt", "liberty tax",
    "planet fitness", "anytime fitness", "la fitness", "24 hour fitness",
    "crunch fitness", "orangetheory", "f45 training", "pure barre",
    "great clips", "supercuts", "sport clips", "fantastic sams",
    "massage envy", "european wax center", "sola salon",
    "enterprise rent", "hertz", "avis", "budget car",
    "uhaul", "u-haul", "penske truck",
    "autozone", "advance auto", "o'reilly auto", "napa auto",
    "pep boys", "firestone", "midas", "jiffy lube", "meineke", "valvoline",
    "super 8", "days inn", "holiday inn", "marriott", "hilton", "hyatt",
    "best western", "la quinta", "comfort inn", "hampton inn",
    "courtyard by", "fairfield inn", "residence inn",
}


def _is_chain(name: str) -> bool:
    """True if the business name matches a known national chain."""
    if not name:
        return False
    low = name.lower()
    return any(brand in low for brand in CHAIN_BLACKLIST)


# ── Precision helpers ─────────────────────────────────────────────────────────

# Higher = more trustworthy. Google Places attributes websites/phones directly
# from the business's Google Business Profile; Yelp is API-backed but lacks
# websites; scrapers pull from listing cards that are often stale.
SOURCE_PRIORITY = {"google": 4, "yelp": 3, "yellowpages": 2, "superpages": 1}

_NAME_NOISE = {
    "the", "and", "of", "a", "an", "&", "+",
    "inc", "inc.", "llc", "ltd", "corp", "corporation", "co", "company",
    "pc", "pllc", "pa", "p.a.", "pllp",
}


def _priority(source: str | None) -> int:
    return SOURCE_PRIORITY.get((source or "").lower(), 0)


def _digits(value: str | None) -> str:
    if not value:
        return ""
    return "".join(c for c in value if c.isdigit())


def _name_tokens(name: str | None) -> set[str]:
    """Tokenize a business name: lowercase, strip punctuation, drop noise words."""
    if not name:
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    return {t for t in cleaned.split() if t and t not in _NAME_NOISE and len(t) > 1}


def _phone_consensus(records: list[dict]) -> str | None:
    """Pick the best phone across multiple records of the same business:
    majority vote on digits, tiebreak by source priority."""
    candidates = [(r, _digits(r.get("phone"))) for r in records]
    candidates = [(r, d) for r, d in candidates if len(d) >= 10]
    if not candidates:
        return None
    counts = Counter(d for _, d in candidates)
    top_digits, top_count = counts.most_common(1)[0]
    if top_count >= 2:
        # Majority — return the original phone string from the highest-priority
        # source that reported it
        winners = [r for r, d in candidates if d == top_digits]
        winners.sort(key=lambda r: -_priority(r.get("source")))
        return winners[0].get("phone")
    # No majority — pick highest-priority source's phone
    candidates.sort(key=lambda rd: -_priority(rd[0].get("source")))
    return candidates[0][0].get("phone")


def _merge_group(records: list[dict]) -> dict:
    """Merge multiple records of the same business into one, preferring
    higher-priority sources. Phone is chosen by consensus."""
    ordered = sorted(records, key=lambda r: -_priority(r.get("source")))
    merged = dict(ordered[0])  # highest-priority record as the base
    for r in ordered[1:]:
        for k, v in r.items():
            if v and not merged.get(k):
                merged[k] = v
    consensus = _phone_consensus(records)
    if consensus:
        merged["phone"] = consensus
    merged["_sources"] = sorted({r.get("source") for r in records if r.get("source")})
    return merged


def _consolidate(raw_businesses: list[dict]) -> list[dict]:
    """Group raw records by normalized (name, city); merge each group to one record."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for b in raw_businesses:
        name = (b.get("business_name") or "").strip().lower()
        city = (b.get("city") or "").strip().lower()
        if not name:
            continue
        groups.setdefault((name, city), []).append(b)
    return [_merge_group(g) for g in groups.values()]


def _verify_html_matches_business(
    html: str, business_name: str, phone: str | None, city: str | None
) -> bool:
    """Return True if the fetched HTML appears to belong to this business.

    Checks (any positive passes):
      1. The last 10 digits of the phone appear in the page's digit stream.
      2. The <title> tag overlaps with the business name tokens.
      3. The body contains ≥70% of the business name tokens (or ≥1 for single-token names).
    """
    if not html:
        return False
    low = html.lower()

    # 1. Phone check — strongest positive signal
    phone_digits = _digits(phone)
    if len(phone_digits) >= 10:
        last10 = phone_digits[-10:]
        if last10 in _digits(low):
            return True

    biz_tokens = _name_tokens(business_name)
    if not biz_tokens:
        return False

    # 2. Title tag check
    title_match = re.search(r"<title[^>]*>(.*?)</title>", low, re.DOTALL)
    if title_match:
        title_tokens = _name_tokens(title_match.group(1))
        overlap = len(biz_tokens & title_tokens)
        if overlap > 0:
            if len(biz_tokens) <= 2:
                return True
            if overlap / len(biz_tokens) >= 0.5:
                return True

    # 3. Body token overlap
    matched = sum(1 for t in biz_tokens if t in low)
    if len(biz_tokens) == 1:
        return matched >= 1
    return (matched / len(biz_tokens)) >= 0.7


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

    # 1a-bis. Google Places — returns website URLs inline, no enrichment needed
    for cat in categories:
        try:
            result = await google_places.search_businesses(cat, location)
            for place in result:
                raw_businesses.append(google_places.normalize(place, cat))
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
            raw_businesses.extend(await superpages.scrape_superpages(cat, location, pages=1))
        except Exception:
            pass

    # Drop national chains — Elenos can't sell web work to their corporate offices
    raw_businesses = [b for b in raw_businesses if not _is_chain(b.get("business_name", ""))]

    # Cross-source consolidation: group by (name, city), merge fields, pick
    # consensus phone. One record per business, regardless of how many
    # sources reported it.
    consolidated = _consolidate(raw_businesses)
    dupes_skipped = len(raw_businesses) - len(consolidated)

    # DB dedup — drop records that already exist, updating them in place when
    # the incoming record has higher source priority.
    new_businesses: list[dict] = []
    for biz in consolidated:
        if await _check_and_merge_duplicate(db, biz):
            dupes_skipped += 1
            continue
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

    # 2c. Google search fallback for leads still missing website URLs
    needs_website = [biz for biz in new_businesses if not biz.get("website_url")]
    if needs_website:
        sem_goog = asyncio.Semaphore(3)

        async def _google_website(biz: dict):
            async with sem_goog:
                url = await _google_search_website(biz["business_name"], biz["city"], biz["state"])
                if url:
                    biz["website_url"] = url

        await asyncio.gather(*[_google_website(b) for b in needs_website], return_exceptions=True)

    # 3. Evaluate and save — sequential, one lead at a time
    # Each lead's HTML and parse tree are GC'd before the next one starts
    new_leads_saved: list[dict] = []

    filtered_out = 0
    async with httpx.AsyncClient(headers=EVAL_HEADERS, timeout=12.0, follow_redirects=True) as client:
        for biz in new_businesses:
            if len(new_leads_saved) >= MAX_LEADS_PER_RUN:
                break
            try:
                lead = await _score_lead(biz, client)
            except Exception:
                continue
            if lead is None:
                filtered_out += 1
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


async def _check_and_merge_duplicate(db, biz: dict) -> bool:
    """Check if a lead already exists. If it does, fill in missing fields and —
    when the incoming record comes from a higher-priority source — overwrite
    phone/website_url/email with the more authoritative values.
    Returns True if the record is a duplicate (caller should skip it).
    """
    phone = biz.get("phone")
    name = biz["business_name"]
    city = biz["city"]

    existing = None
    select_cols = "id, source, phone, website_url, email"

    if phone:
        try:
            r = db.table("leads").select(select_cols).eq("phone", phone).limit(1).execute()
            if r.data:
                existing = r.data[0]
        except Exception:
            pass

    if not existing:
        try:
            r = (
                db.table("leads")
                .select(select_cols)
                .ilike("business_name", name)
                .ilike("city", city)
                .limit(1)
                .execute()
            )
            if r.data:
                existing = r.data[0]
        except Exception:
            pass

    if not existing:
        return False  # not a duplicate

    update: dict = {}

    # Always fill a missing website_url regardless of priority
    if biz.get("website_url") and not existing.get("website_url"):
        update["website_url"] = biz["website_url"]

    # Overwrite conflicting fields when the incoming source outranks the existing
    incoming_p = _priority(biz.get("source"))
    existing_p = _priority(existing.get("source"))
    if incoming_p > existing_p:
        for field in ("phone", "website_url", "email"):
            incoming_val = biz.get(field)
            if incoming_val and incoming_val != existing.get(field):
                update[field] = incoming_val
        if update:
            update["source"] = biz.get("source")

    if update:
        try:
            db.table("leads").update(update).eq("id", existing["id"]).execute()
        except Exception:
            pass

    return True


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

    # 1a-bis. Google Places
    for cat in categories:
        yield _evt("log", "google", f"Searching Google Places for {cat}...")
        try:
            result = await google_places.search_businesses(cat, location)
            count = len(result)
            for place in result:
                raw_businesses.append(google_places.normalize(place, cat))
            yield _evt("log", "google", f"Found {count} from Google Places ({cat})")
        except Exception:
            yield _evt("log", "google", f"Google Places search failed for {cat}")

    # 1b. Scrapers
    scraper_sources = [
        ("yellowpages", "Yellow Pages", lambda cat: scraper.scrape_yellowpages(cat, location, pages=1)),
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

    # Drop national chains
    before = len(raw_businesses)
    raw_businesses = [b for b in raw_businesses if not _is_chain(b.get("business_name", ""))]
    chains_dropped = before - len(raw_businesses)
    if chains_dropped:
        yield _evt("log", "filter", f"Filtered out {chains_dropped} national chain(s)")

    # 2. Consolidate cross-source records (phone consensus + field merging)
    yield _evt("log", "dedup", "Consolidating across sources and deduplicating...")
    consolidated = _consolidate(raw_businesses)
    in_batch_merged = len(raw_businesses) - len(consolidated)
    if in_batch_merged:
        yield _evt("log", "dedup", f"Merged {in_batch_merged} cross-source duplicate(s)")

    # DB dedup
    new_businesses: list[dict] = []
    dupes_skipped = in_batch_merged
    for biz in consolidated:
        if await _check_and_merge_duplicate(db, biz):
            dupes_skipped += 1
            continue
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

    # 2c. Google search fallback for leads still missing website URLs
    needs_website = [biz for biz in new_businesses if not biz.get("website_url")]
    if needs_website:
        yield _evt("log", "enrich", f"Google searching for {len(needs_website)} missing website URLs...")
        sem_goog = asyncio.Semaphore(3)

        async def _google_website(biz: dict):
            async with sem_goog:
                url = await _google_search_website(biz["business_name"], biz["city"], biz["state"])
                if url:
                    biz["website_url"] = url

        await asyncio.gather(*[_google_website(b) for b in needs_website], return_exceptions=True)
        found = sum(1 for b in needs_website if b.get("website_url"))
        yield _evt("log", "enrich", f"Google found {found}/{len(needs_website)} website URLs")

    # 3. Evaluate, research, and save — filter out leads with good websites
    to_score = min(len(new_businesses), MAX_LEADS_PER_RUN)
    yield _evt("log", "research", f"Evaluating & researching {to_score} leads...")
    new_leads_saved: list[dict] = []
    filtered_out = 0

    async with httpx.AsyncClient(headers=EVAL_HEADERS, timeout=12.0, follow_redirects=True) as client:
        for i, biz in enumerate(new_businesses):
            if len(new_leads_saved) >= MAX_LEADS_PER_RUN:
                break
            yield _evt("progress", "research",
                        f"Evaluating {i + 1}/{to_score}: {biz['business_name']}",
                        progress={"current": i + 1, "total": to_score})
            try:
                lead = await _score_lead(biz, client)
            except Exception:
                continue

            if lead is None:
                filtered_out += 1
                yield _evt("log", "research",
                            f"Filtered out: {biz['business_name']} (good website, not a prospect)")
                continue

            # Log what we found
            found = []
            if lead.get("email"):
                found.append("email")
            if lead.get("contact_name"):
                found.append(f"contact: {lead['contact_name']}")
            if lead.get("social_links"):
                found.append(f"{len(lead['social_links'])} social")
            detail = f" — found {', '.join(found)}" if found else ""
            yield _evt("log", "research",
                        f"Score {lead['score']}/10: {biz['business_name']}{detail}")

            try:
                db.table("leads").insert(lead).execute()
                new_leads_saved.append(lead)
            except Exception:
                continue

    if filtered_out:
        yield _evt("log", "research", f"Filtered out {filtered_out} leads with good websites")

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


MIN_SCORE = 5  # Only save leads with score >= 5 (worse website = higher score = better prospect)


async def _score_lead(biz: dict, client: httpx.AsyncClient) -> dict | None:
    """Evaluate and enrich a lead. Returns None if the lead doesn't qualify."""
    website_url = biz.get("website_url")
    homepage_html = ""
    score_data: dict = {}
    email = None

    # Always extract from raw_data (no HTTP)
    enrichment = deep_researcher.extract_from_raw_data(biz)

    if website_url:
        score_data = await evaluator.evaluate(website_url, client)
        homepage_html = score_data.pop("homepage_html", "")

        # Verify the URL actually belongs to this business. Google Places
        # attributes websites directly so we trust them without verification;
        # every other path (Yelp listing scrape, Yellow Pages/Superpages,
        # DuckDuckGo fallback) can return misattributed URLs.
        first_party = biz.get("source") == "google"
        if not first_party and not _verify_html_matches_business(
            homepage_html, biz["business_name"], biz.get("phone"), biz.get("city")
        ):
            # Can't confirm this is the right business's site — discard it
            # rather than harvest emails/content that might belong to a
            # different company with a similar name.
            website_url = None
            homepage_html = ""
            score_data = {}

    if not website_url:
        score_data = {"score": 10, "score_reason": "No verifiable website found"}
    else:
        # Filter early — don't waste time on leads with good websites
        if score_data["score"] < MIN_SCORE:
            return None
        email = await email_extractor.extract_email(website_url, homepage_html, client)

    # Fallback email hunt — only when we have a verified website or none at all.
    # (Unverified URLs were set to None above, so find_email_for_lead falls
    # back to Facebook/DDG/Yelp-listing lookups by business name.)
    if not email:
        try:
            fallback = await email_extractor.find_email_for_lead(
                business_name=biz["business_name"],
                city=biz["city"],
                state=biz["state"],
                website_url=website_url,
                phone=biz.get("phone"),
            )
            if fallback.get("email"):
                email = fallback["email"]
        except Exception:
            pass

        # Deep research — contact names, social links, extra emails/phones.
        # Only runs when we have verified homepage HTML.
        if homepage_html:
            try:
                web_enrichment = await deep_researcher.deep_research(biz, homepage_html, client)
                enrichment.update(web_enrichment)
            except Exception:
                pass

    lead = {
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

    # Merge enrichment fields
    for key in ("contact_name", "contact_title", "additional_phones", "additional_emails",
                "social_links", "business_hours", "rating", "review_count",
                "years_in_business", "bbb_accredited", "yelp_categories", "address"):
        if key in enrichment:
            lead[key] = enrichment[key]

    # If no primary email was found but deep research found additional emails, promote one
    if not lead["email"] and lead.get("additional_emails"):
        lead["email"] = lead["additional_emails"][0]
        lead["additional_emails"] = [e for e in lead["additional_emails"] if e != lead["email"]]

    return lead


async def _google_search_website(name: str, city: str, state: str) -> str | None:
    """Search DuckDuckGo for a business website URL as a last-resort fallback.

    If the top result is a Facebook business page, scrapes it for the
    business's actual website URL.  Returns the real website when possible,
    otherwise the Facebook URL so we can still extract email/info later.
    """
    query = quote_plus(f"{name} {city} {state}")
    url = f"https://html.duckduckgo.com/html/?q={query}"
    # Directories / aggregators we always skip
    _SKIP_DOMAINS = {
        "yelp.com", "yellowpages.com", "bbb.org", "manta.com",
        "superpages.com", "mapquest.com", "google.com", "bing.com",
        "apple.com", "tripadvisor.com", "angi.com", "thumbtack.com",
        "duckduckgo.com",
    }
    # Social platforms — we'll keep Facebook but skip others
    _SOCIAL_SKIP = {"instagram.com", "twitter.com", "x.com", "linkedin.com",
                    "youtube.com", "tiktok.com", "pinterest.com"}
    try:
        async with httpx.AsyncClient(headers=EVAL_HEADERS, timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text[:100_000], "html.parser")

            facebook_url = None

            for a_tag in soup.find_all("a", class_="result__a", href=True):
                href = a_tag["href"]
                # DDG wraps links: //duckduckgo.com/l/?uddg=<encoded_url>&...
                if "uddg=" in href:
                    from urllib.parse import unquote as url_unquote
                    href = url_unquote(href.split("uddg=")[1].split("&")[0])
                try:
                    parsed = urlparse(href)
                    domain = parsed.netloc.lower().removeprefix("www.")
                except Exception:
                    continue
                if not (parsed.scheme in ("http", "https") and domain and "." in domain):
                    continue
                if domain in _SKIP_DOMAINS:
                    continue
                if domain in _SOCIAL_SKIP:
                    continue

                # If it's a Facebook business page, remember it but keep looking
                # for an actual business website first
                if "facebook.com" in domain:
                    if not facebook_url:
                        facebook_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
                    continue

                # Found a non-directory, non-social link — likely the real website
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

            # No direct website found — try to extract from Facebook page
            if facebook_url:
                real_url = await _extract_website_from_facebook(facebook_url, client)
                if real_url:
                    return real_url
                # Return the Facebook URL itself so we can at least scrape it
                return facebook_url

    except Exception:
        pass
    return None


async def _extract_website_from_facebook(fb_url: str, client: httpx.AsyncClient) -> str | None:
    """Scrape a Facebook business page for the linked website URL.

    Uses headless Chrome since Facebook blocks plain HTTP requests.
    """
    from urllib.parse import unquote
    import re

    _SKIP = {"instagram.com", "twitter.com", "x.com", "youtube.com",
             "tiktok.com", "facebook.com", "google.com", "yelp.com",
             "linkedin.com", "pinterest.com", "fb.com", "fbcdn.net"}

    try:
        from agent.browser import scrape_page
        result = await scrape_page(fb_url)
        if not result.get("success"):
            return None

        # Check links returned by the browser (already resolved by JS)
        for link in result.get("links", []):
            try:
                parsed = urlparse(link)
                domain = parsed.netloc.lower().removeprefix("www.")
            except Exception:
                continue
            if (parsed.scheme in ("http", "https")
                    and domain and "." in domain
                    and domain not in _SKIP):
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

        # Also check for l.facebook.com redirect URLs in raw page text
        redirect_pattern = re.compile(r'l\.facebook\.com/l\.php\?u=([^&"]+)')
        for match in redirect_pattern.findall(result.get("text", "")):
            decoded = unquote(match)
            try:
                parsed = urlparse(decoded)
                domain = parsed.netloc.lower().removeprefix("www.")
            except Exception:
                continue
            if (parsed.scheme in ("http", "https")
                    and domain and "." in domain
                    and domain not in _SKIP):
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    except Exception:
        pass
    return None
