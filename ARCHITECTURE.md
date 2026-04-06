# LeadGen — Architecture & Technology Reference

> **Keep this file updated** whenever services, routes, models, or data flows change.
> Last updated: 2026-04-05

---

## What This Does

LeadGen is an AI-powered outreach agent for **Elenos AI** (founder: Edward Jones).

It automatically:
1. Scrapes business directories for local businesses
2. Scores each business's website quality (bad website = hot prospect)
3. Extracts contact emails from their websites
4. Uses AI to analyze *why* the website is bad
5. Generates and sends a personalized cold email via that analysis
6. Follows up automatically at 3 days and 7 days if no response
7. Can generate a complete website spec/brief for any converted lead

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | **Python 3.12 + FastAPI** | REST API, business logic, scraping orchestration |
| AI | **Groq API** (`llama-3.3-70b-versatile`) | Website analysis, email generation, website specs |
| Email Sending | **Resend** | Transactional email delivery |
| Database | **Supabase** (PostgreSQL) | Lead storage, email history, schedules |
| Scheduler | **APScheduler** (AsyncIOScheduler) | Scheduled searches + automated follow-ups |
| Scraping | **httpx + BeautifulSoup4** | HTML fetching and parsing |
| Frontend | **Next.js 16 (TypeScript)** | UI dashboard |
| Frontend State | **TanStack React Table** | Sortable, filterable leads table |
| Styling | **Tailwind CSS** | Dark theme UI |

---

## Directory Structure

```
LeadGen/
├── ARCHITECTURE.md          ← this file
├── CLAUDE.md                ← AI assistant instructions
├── supabase_schema.sql      ← full DB schema + migration SQL
│
├── backend/
│   ├── .env                 ← secrets (never commit)
│   ├── requirements.txt
│   └── app/
│       ├── main.py          ← FastAPI app, CORS, lifespan
│       ├── config.py        ← env var settings (Pydantic)
│       ├── database.py      ← Supabase client singleton
│       ├── scheduler.py     ← APScheduler: search schedules + follow-up jobs
│       ├── models/
│       │   └── lead.py      ← Pydantic models: Lead, LeadUpdate, EmailRecord, etc.
│       ├── routers/
│       │   ├── leads.py     ← CRUD on leads table
│       │   ├── search.py    ← POST /api/search triggers a run
│       │   ├── scheduler.py ← CRUD on search_schedules table
│       │   └── outreach.py  ← AI analysis, email send, history, site generator
│       └── services/
│           ├── yelp.py           ← Yelp Fusion API (paginated, up to 1000/category)
│           ├── scraper.py        ← Yellow Pages scraper (BeautifulSoup)
│           ├── bbb.py            ← Better Business Bureau scraper
│           ├── manta.py          ← Manta directory scraper
│           ├── superpages.py     ← Superpages scraper
│           ├── lead_processor.py ← Main pipeline: fetch → dedupe → score → save
│           ├── evaluator.py      ← Website quality scorer (1–10)
│           ├── email_extractor.py← Email discovery from website HTML
│           ├── ai_analyzer.py    ← Groq: structured website analysis
│           ├── email_generator.py← Groq: personalized cold email + follow-ups
│           ├── email_sender.py   ← Resend API wrapper
│           └── website_generator.py ← Groq: full website spec/brief
│
└── frontend/
    ├── app/
    │   ├── page.tsx         ← Root layout, global state management
    │   └── globals.css
    ├── components/
    │   ├── LeadsTable.tsx   ← Sortable/filterable table (TanStack)
    │   ├── LeadDetailPanel.tsx ← Right sidebar: score, outreach, email history
    │   ├── SearchPanel.tsx  ← Left sidebar: location + category picker
    │   ├── ScoreBadge.tsx   ← Score pill (purple/red/amber/zinc)
    │   └── StatusBadge.tsx  ← New/Contacted/Closed badge
    ├── hooks/
    │   ├── useLeads.ts      ← Fetch, update, delete leads from API
    │   └── useSearch.ts     ← Trigger searches, track loading/error
    └── lib/
        ├── api.ts           ← All HTTP calls to the backend
        ├── types.ts         ← TypeScript interfaces (Lead, AiAnalysis, etc.)
        └── constants.ts     ← Category list, status labels
```

---

## Data Flow

### 1. Lead Generation (Search)

```
User clicks "Run Search"
        │
        ▼
POST /api/search {location, categories}
        │
        ▼
lead_processor.run_search()
        │
        ├─ yelp.search_businesses()        Yelp Fusion API (up to 200/category)
        ├─ scraper.scrape_yellowpages()    HTML scraping (blocked by Cloudflare currently)
        ├─ bbb.scrape_bbb()               HTML scraping
        ├─ manta.scrape_manta()           HTML scraping
        └─ superpages.scrape_superpages() HTML scraping
        │
        ▼
Deduplication (in-memory batch + DB indexed queries)
  - Within batch: keyed on (name.lower(), city.lower())
  - Against DB: phone UNIQUE index + name+city ILIKE
        │
        ▼
For each new business:
  evaluator.evaluate(website_url)
    - Fetches homepage HTML (50KB cap, 10s timeout)
    - Checks: HTTPS, load speed, viewport meta, meta description,
              page title, copyright year, outdated platform
    - Returns score 1–10 (higher = worse website = hotter lead)
        │
        ▼
  email_extractor.extract_email(url, html)
    - Searches homepage HTML for email addresses
    - Falls back to /contact and /contact-us pages
    - Prefers business-domain emails over gmail/yahoo
        │
        ▼
  INSERT into leads table (Supabase)
        │
        ▼
Return {run_id, new_leads, dupes_skipped, leads[]}
```

### 2. AI Outreach (Per Lead)

```
User clicks "Analyze & Send Email" in LeadDetailPanel
        │
        ▼
POST /api/outreach/{lead_id}/send
        │
        ├─ If ai_analysis is null:
        │    Re-fetch homepage HTML (50KB cap)
        │    ai_analyzer.analyze_website()
        │      → Groq llama-3.3-70b-versatile
        │      → Returns: {summary, problems[], severity, personalization_hooks[]}
        │      → Saved to leads.ai_analysis (JSONB)
        │
        ├─ email_generator.generate_initial_email()  (or generate_followup_email)
        │    → Groq: 150–200 word personalized cold email
        │    → References specific website problems by name
        │    → Returns {subject, body}
        │
        ├─ email_sender.send_email(to, subject, body)
        │    → Resend API
        │    → Returns {id, status, error}
        │
        ├─ INSERT into email_outreach table
        │
        └─ UPDATE leads:
             outreach_status = "emailed_1"
             last_emailed_at = now()
             status = "Contacted" (if was "New")
```

### 3. Automated Follow-ups (Scheduler)

```
APScheduler — every 6 hours:
_check_and_send_followups()
        │
        ├─ Query: outreach_status="emailed_1" AND follow_up_count=0
        │         AND last_emailed_at <= now - 3 days
        │    → send follow-up 1 (100-word email, acknowledges no response)
        │    → outreach_status → "emailed_2"
        │
        └─ Query: outreach_status="emailed_2" AND follow_up_count=1
                  AND last_emailed_at <= now - 7 days
           → send follow-up 2
           → outreach_status → "emailed_3" (done)
```

### 4. Website Generator (On Demand)

```
User clicks "Generate website spec"
        │
        ▼
POST /api/outreach/{lead_id}/generate-site
        │
        ▼
website_generator.generate_website_spec()
  → Groq llama-3.3-70b-versatile (2048 tokens)
  → Returns full website brief:
      tagline, hero headline, hero subheadline,
      sections (Services/About/Contact/etc.),
      color palette (hex), design direction,
      SEO title, meta description, suggested domain
        │
        ▼
Rendered in LeadDetailPanel — "Copy JSON" button
```

---

## Database Schema

### `leads` (main table)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| business_name | TEXT | |
| city | TEXT | |
| state | TEXT | |
| phone | TEXT UNIQUE | nullable |
| email | TEXT | nullable, extracted from website |
| website_url | TEXT | nullable |
| score | INTEGER | 1–10, higher = worse website |
| score_reason | TEXT | semicolon-separated list of issues |
| status | TEXT | `New` / `Contacted` / `Closed` — human CRM field |
| category | TEXT | e.g. "restaurants" |
| source | TEXT | yelp / yellowpages / bbb / manta / superpages |
| raw_data | JSONB | original API/scrape response |
| ai_analysis | JSONB | `{summary, problems[], severity, personalization_hooks[]}` |
| outreach_status | TEXT | `idle→queued→emailed_1→emailed_2→emailed_3` or `bounced/opted_out` |
| last_emailed_at | TIMESTAMPTZ | when most recent email was sent |
| follow_up_count | INTEGER | 0=none sent, 1=FU1 sent, 2=FU2 sent |
| created_at | TIMESTAMPTZ | auto |
| updated_at | TIMESTAMPTZ | auto-updated via trigger |

**Unique indexes:** `phone` (where not null), `(lower(business_name), lower(city))`

### `email_outreach`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| lead_id | UUID FK | → leads.id, CASCADE delete |
| sequence_step | INTEGER | 0=initial, 1=follow-up 1, 2=follow-up 2 |
| subject | TEXT | |
| body | TEXT | |
| sent_at | TIMESTAMPTZ | null if failed |
| resend_id | TEXT | Resend message ID, used for webhook lookups |
| status | TEXT | `pending / sent / failed / opened` |
| error_message | TEXT | populated on failure |
| created_at | TIMESTAMPTZ | |

### `search_runs`

Audit log of every search execution. Stores `location`, `categories[]`, `total_found`, `new_leads`, `dupes_skipped`, timestamps.

### `search_schedules`

Recurring search configs. Each row has a 5-part cron expression (e.g. `0 8 * * *` = 8am daily), location, categories, enabled flag. Loaded by APScheduler on startup.

---

## API Endpoints

### Leads
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/leads` | List leads (filter by status/category/min_score, sort, paginate) |
| GET | `/api/leads/{id}` | Single lead |
| PATCH | `/api/leads/{id}` | Update status, email, or outreach_status |
| DELETE | `/api/leads/{id}` | Remove lead |
| GET | `/api/leads/export` | CSV download |

### Search
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/search` | Trigger a search run `{location, categories}` |

### Schedules
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/schedules` | List all schedules |
| POST | `/api/schedules` | Create schedule `{name, location, categories, cron_expression}` |
| PATCH | `/api/schedules/{id}` | Enable/disable |
| DELETE | `/api/schedules/{id}` | Remove |

### Outreach
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/outreach/{id}/analyze` | Run AI website analysis, save to leads.ai_analysis |
| POST | `/api/outreach/{id}/send` | Full pipeline: analyze → generate → send. Body: `{dry_run: bool}` |
| GET | `/api/outreach/{id}/emails` | Email history for a lead |
| POST | `/api/outreach/{id}/generate-site` | Generate website spec (not saved to DB) |
| POST | `/api/outreach/webhooks/resend` | Resend open/bounce webhook handler |

---

## Scoring Logic (`evaluator.py`)

Score 1–10 built from penalties. **Higher score = worse website = hotter lead.**

| Signal | Penalty | Reason Shown |
|--------|---------|-------------|
| No HTTPS | +3 | "No SSL certificate (HTTP only)" |
| Timeout / connection failure | +5 | "Website unreachable (timeout)" |
| HTTP 4xx/5xx | +4 | "Website returns error (NNN)" |
| Load time > 6s | +3 | "Very slow page load (X.Xs)" |
| Load time > 3s | +2 | "Slow page load (X.Xs)" |
| No viewport meta tag | +2 | "Not mobile optimized" |
| No meta description | +1 | "Missing meta description (SEO gap)" |
| No page title | +1 | "No descriptive page title" |
| Copyright year < 2019 | +2 | "Severely outdated copyright year" |
| Copyright year 2019–2021 | +1 | "Outdated copyright year" |
| Old platform detected | +1 | "Built on outdated platform (name)" |
| No website at all | 10 | "No website found" |

Old platforms detected: WordPress 3.x/4.x/5.0/5.1, Jimdo, Webs.com, Yola, Homestead, Angelfire.

---

## Environment Variables

File: `backend/.env`

```
YELP_API_KEY=...          Yelp Fusion API key
SUPABASE_URL=...          Supabase project URL
SUPABASE_KEY=...          Supabase anon key
GROQ_API_KEY=...          Groq API key (free at console.groq.com)
RESEND_API_KEY=...        Resend API key (resend.com) — optional until email sending needed
FROM_EMAIL=...            Sender address for outreach emails — optional until email sending needed
```

---

## Lead Statuses

Two separate status fields exist on every lead:

| Field | Values | Managed by |
|-------|--------|-----------|
| `status` | `New → Contacted → Closed` | Human (via UI status buttons) |
| `outreach_status` | `idle → queued → emailed_1 → emailed_2 → emailed_3` (or `bounced`, `opted_out`) | Automation (outreach router + scheduler) |

These are intentionally decoupled: a lead can be marked `Closed` by a human without any automated emails having been sent, and vice versa.

---

## Frontend UI

### Layout (page.tsx)
```
┌─ Header: logo, last run stats, total lead count ──────────────────┐
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SearchPanel (270px)  │  LeadsTable (flex)  │  LeadDetailPanel    │
│                       │                     │  (352px, when open) │
│  - Location input     │  - Score column      │                     │
│  - Category picker    │  - Business name     │  - Lead score       │
│  - Run button         │  - Location          │  - AI analysis      │
│                       │  - Phone             │  - Outreach action  │
│                       │  - Email/website dot │  - Email history    │
│                       │  - Outreach dot      │  - Website spec     │
│                       │  - Source badge      │  - Status buttons   │
│                       │  - Status badge      │  - Contact info     │
└───────────────────────────────────────────────────────────────────┘
```

### LeadDetailPanel sections (in order)
1. **Header** — business name, category, city/state, close button
2. **Lead Score** — score badge, score bar, tier label, issue tags
3. **AI Analysis** — summary, problem pills by category, severity badge
4. **Status** — New / Contacted / Closed buttons
5. **Outreach** — outreach_status pill, "Analyze & Send" / "Send Follow-up" button, dry-run preview
6. **Email History** — lazy-loaded, expandable email bodies
7. **Website Generator** — generates full website brief, Copy JSON button
8. **Details** — source, category, created date
9. **Footer** — delete button

---

## Known Limitations

- **Directory scrapers (YP, BBB, Manta, Superpages) are blocked by Cloudflare** — returning 0 results. Yelp is the active data source.
- **Yelp doesn't return business website URLs** — leads from Yelp get score 10 ("No website found") unless a scraper cross-references a URL.
- `RESEND_API_KEY` and `FROM_EMAIL` must be set before the send button does anything real. "Preview email (dry run)" works without them.
- DB migration must be run in Supabase SQL editor before outreach features work (see `supabase_schema.sql`).

---

## Running Locally

```bash
# Backend (from /backend)
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Frontend (from /frontend)
npm install
npm run dev
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
