# LeadGen — CLAUDE.md

## Project Overview
An internal lead generation tool built for **Elenos AI** (founder: Edward Jones).
It scrapes business directories, scores leads based on website quality, and stores them in Supabase.
The goal is to identify businesses with poor/outdated websites as prospects for Elenos AI's web/automation services.

## Architecture

```
LeadGen/
├── backend/              # FastAPI Python backend
│   ├── app/
│   │   ├── main.py           # FastAPI app, CORS config
│   │   ├── config.py         # Pydantic settings (env vars)
│   │   ├── database.py       # Supabase client
│   │   ├── models/lead.py    # Pydantic models (Lead, SearchRequest, etc.)
│   │   ├── routers/
│   │   │   ├── search.py     # POST /api/search — triggers a search run
│   │   │   └── leads.py      # CRUD on leads table
│   │   └── services/
│   │       ├── yelp.py           # Yelp Fusion API (requires API key)
│   │       ├── scraper.py        # Yellow Pages scraper (BeautifulSoup)
│   │       ├── lead_processor.py # Orchestrates fetch → dedupe → score → save
│   │       ├── evaluator.py      # Website quality scorer (1–10, higher = worse)
│   │       └── email_extractor.py # Email discovery from business websites
│   └── requirements.txt
├── frontend/             # Next.js frontend (TypeScript)
└── supabase_schema.sql   # DB schema (leads + search_runs tables)
```

## Data Flow
1. `POST /api/search` with `{location, categories}` triggers `run_search()`
2. Yelp API fetches up to 150 businesses per category (3 paginated calls)
3. Yellow Pages scrapes 2 pages per category
4. Results are deduped against existing DB records (by phone + name+city)
5. Each new business gets scored by `evaluator.py` (fetches website, checks SSL, load time, viewport, meta desc, copyright year, old platforms)
6. Email extractor tries homepage + contact/about pages
7. All new leads are inserted into Supabase `leads` table
8. Search run metadata saved to `search_runs` table

## Database (Supabase/PostgreSQL)
- `leads` — main table, unique on `phone` and `(lower(business_name), lower(city))`
- `search_runs` — audit log per search execution
- Schema file: `supabase_schema.sql`

## Scoring Logic (`evaluator.py`)
Score 1–10, **higher = worse website = better lead for Elenos**.
Penalties for: no HTTPS, timeout/unreachable, slow load, no viewport meta, no meta description, no title, outdated copyright year, old platform (Jimdo, Webs.com, Yola, etc.)

## Sources
| Source | Method | Notes |
|--------|--------|-------|
| Yelp | Official API (Fusion) | Requires `YELP_API_KEY`. Up to 1000/category (20 paginated calls). Does NOT return business website URLs. |
| Yellow Pages | HTML scraping | 5 pages/category, polite 1.5–2.5s delay |
| BBB | HTML scraping + `__NEXT_DATA__` JSON (Next.js) | 3 pages/category. Parses Next.js JSON first, HTML fallback |
| Manta | HTML scraping | 3 pages/category |
| Superpages | HTML scraping | 3 pages/category (same parent company as YP — similar structure) |

## Scheduling
- APScheduler (`AsyncIOScheduler`) runs inside the FastAPI process
- On startup, loads all enabled schedules from `search_schedules` Supabase table
- `POST /api/schedules` — create a schedule (5-part cron expression, e.g. `"0 8 * * *"`)
- `GET /api/schedules` — list all
- `PATCH /api/schedules/{id}` — enable/disable
- `DELETE /api/schedules/{id}` — remove
- Manual trigger: `POST /api/search` (unchanged)

## Key Fixes Applied
- **Dedup merge bug fixed**: Yelp records win dedup order but lack website URLs. If a later source (YP, BBB, etc.) has a website for the same business, it now gets merged in instead of dropped.
- **Yelp pagination**: Increased from 150 to 1000 max per category.
- **Evaluation semaphore**: Increased from 5 to 10 concurrent website checks.

## Environment Variables
```
YELP_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
```
See `backend/.env.example`

## Tech Stack
- Backend: Python, FastAPI, httpx, BeautifulSoup4, lxml, Supabase Python SDK
- Frontend: Next.js (TypeScript)
- Database: Supabase (PostgreSQL)
- Hosting: local dev, Vercel (frontend)

## Key Conventions
- Yelp `normalize()` intentionally leaves `website_url: None` — YP scraper or email extractor fills it
- Semaphore of 5 for concurrent website evaluation
- All scraping uses a real Chrome user-agent to reduce blocking
- Deduplication happens in-memory before DB insert to minimize round trips
