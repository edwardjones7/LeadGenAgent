# LeadGen — AI-Powered Cold Outreach Agent

> **Find local businesses with bad websites. Analyze why. Send a personalized email. Close the deal.**

LeadGen is an autonomous lead generation and outreach system built for web design agencies. It scrapes business directories, scores each business's website quality using a custom heuristic engine, uses AI to diagnose the exact problems, and fires off personalized cold emails — then follows up automatically if there's no response.

---

## How It Works

```
Scrape directories → Score website quality → AI analysis → Generate email → Send → Auto follow-up
```

1. **Discover** — Pulls businesses from Yelp, Yellow Pages, BBB, Manta, and Superpages
2. **Score** — Rates each website 1–10 (higher = worse site = hotter lead) based on SSL, load speed, mobile optimization, SEO signals, and platform age
3. **Analyze** — Uses LLaMA 3.3 70B (via Groq) to write a structured breakdown of *why* the website is bad
4. **Outreach** — Generates a 150–200 word personalized cold email that references the specific problems found
5. **Follow-up** — Automatically sends follow-up emails at 3 days and 7 days if no reply
6. **Convert** — On interested leads, generates a full website spec/brief ready to pitch

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + FastAPI |
| AI | Groq API (`llama-3.3-70b-versatile`) |
| Email | Resend |
| Database | Supabase (PostgreSQL) |
| Scheduler | APScheduler |
| Scraping | httpx + BeautifulSoup4 |
| Frontend | Next.js 16 (TypeScript) |
| UI Components | TanStack React Table + Tailwind CSS |

---

## Features

- **Multi-source scraping** — Yelp Fusion API + HTML scrapers for 4 other directories, with deduplication across all sources
- **Website quality scorer** — 11-signal heuristic engine with per-issue penalties and human-readable reason tags
- **AI website analysis** — Structured JSON output: `{summary, problems[], severity, personalization_hooks[]}`
- **Personalized email generation** — Each email references the business by name and cites specific problems from the analysis
- **Automated follow-up sequences** — Scheduler polls every 6 hours; sends FU1 at 3 days, FU2 at 7 days
- **Website spec generator** — On-demand: full brief with tagline, hero copy, section structure, color palette, SEO meta, and domain suggestions
- **CRM-lite dashboard** — Sortable/filterable leads table with status management (New → Contacted → Closed), email history, and dry-run email preview
- **CSV export** — Download all leads at any time

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- A [Supabase](https://supabase.com) project
- A [Groq](https://console.groq.com) API key (free)
- A [Yelp Fusion](https://www.yelp.com/developers) API key
- A [Resend](https://resend.com) account *(optional until you're ready to send)*

### 1. Database Setup

Run `supabase_schema.sql` in your Supabase SQL editor to create all tables and indexes.

### 2. Backend

```bash
cd backend
cp .env.example .env   # fill in your keys
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

- **Frontend:** http://localhost:3000
- **Backend:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

### Environment Variables

```env
YELP_API_KEY=        # Yelp Fusion API key
SUPABASE_URL=        # Your Supabase project URL
SUPABASE_KEY=        # Supabase anon key
GROQ_API_KEY=        # Groq API key
RESEND_API_KEY=      # Resend API key (optional)
FROM_EMAIL=          # Sender address for outreach (optional)
```

---

## Scoring Logic

Website quality is scored 1–10. **Higher score = worse website = hotter prospect.**

| Signal | Penalty |
|---|---|
| No HTTPS | +3 |
| Website unreachable / timeout | +5 |
| HTTP 4xx/5xx error | +4 |
| Load time > 6s | +3 |
| Load time > 3s | +2 |
| Not mobile optimized | +2 |
| Outdated copyright year (2019–2021) | +1 |
| Severely outdated copyright year (< 2019) | +2 |
| Missing meta description | +1 |
| No page title | +1 |
| Built on outdated platform | +1 |
| No website at all | 10 |

Outdated platforms flagged: WordPress 3.x/4.x/5.0/5.1, Jimdo, Webs.com, Yola, Homestead, Angelfire.

---

## Project Structure

```
LeadGen/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI entry point
│       ├── scheduler.py         # APScheduler: search schedules + follow-ups
│       ├── routers/
│       │   ├── leads.py         # CRUD endpoints
│       │   ├── search.py        # Trigger a search run
│       │   ├── scheduler.py     # Manage recurring schedules
│       │   └── outreach.py      # AI analysis, email send, site generator
│       └── services/
│           ├── yelp.py          # Yelp Fusion API
│           ├── evaluator.py     # Website quality scorer
│           ├── email_extractor.py
│           ├── ai_analyzer.py   # Groq: website analysis
│           ├── email_generator.py
│           ├── email_sender.py  # Resend wrapper
│           └── website_generator.py
└── frontend/
    └── components/
        ├── LeadsTable.tsx       # Sortable/filterable table
        ├── LeadDetailPanel.tsx  # Score, outreach, email history
        └── SearchPanel.tsx      # Location + category picker
```

---

## Known Limitations

- **Yellow Pages, BBB, Manta, and Superpages scrapers are currently blocked by Cloudflare** — Yelp is the active data source
- **Yelp doesn't return website URLs** — leads sourced from Yelp default to score 10 ("No website found") unless a website is found via another method
- Email sending requires `RESEND_API_KEY` and `FROM_EMAIL` to be set. The "Preview (dry run)" mode works without them.

---

## Roadmap

- [ ] Proxy rotation to unblock directory scrapers
- [ ] Webhook-based open/reply tracking (Resend webhooks are stubbed in)
- [ ] Lead import from CSV
- [ ] Multi-user support with workspace isolation
- [ ] Chrome extension for manual lead capture

---

## License

MIT
