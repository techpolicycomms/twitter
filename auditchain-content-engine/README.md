# AuditChain Content Engine

> AI-powered social media content generation and scheduling for the AuditChain platform.
> Uses Claude (Anthropic) to generate LinkedIn posts, Twitter threads, and blog articles
> from a content calendar, with daily RSS news scanning for rapid-response opportunities.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     APScheduler (cron)                       │
│  06:00 UTC → RSS Scan + AI Relevance Analysis               │
│  07:00 UTC → Calendar Content Generation                    │
└─────────┬───────────────────────────┬──────────────────────┘
          │                           │
          ▼                           ▼
┌─────────────────┐       ┌──────────────────────┐
│  RSS Scanner    │       │  Content Generator   │
│  (httpx +       │       │  (Anthropic Claude   │
│   feedparser)   │       │   claude-sonnet-4-5) │
│  5 feeds:       │       │  Platforms:          │
│  • MIT Tech Rev │       │  • LinkedIn (200-300w)│
│  • TechCabal    │       │  • Twitter (4-6 tweet)│
│  • Inc42        │       │  • Blog (800-1200w)  │
│  • OECD AI      │       └──────────┬───────────┘
│  • EU AI Act    │                  │
└─────────┬───────┘                  │
          │ relevance score          │
          ▼                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL (SQLAlchemy)                    │
│  ContentCalendarEntry → GeneratedContent → EngagementMetric │
│  NewsItem → GeneratedContent (rapid response)               │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                   ┌──────────────────┐
                   │  FastAPI +       │
                   │  Jinja2          │
                   │  Dashboard       │
                   │  :8080           │
                   └──────────────────┘
                              │
                              ▼
                   ┌──────────────────┐
                   │  Buffer API      │
                   │  JSON Export     │
                   │  (scheduling)    │
                   └──────────────────┘
```

## Quick Start

### 1. Install dependencies

```bash
cd auditchain-content-engine
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — minimum required:
#   ANTHROPIC_API_KEY=sk-ant-...
#   DATABASE_URL=postgresql+asyncpg://...
```

### 3. Start with Docker (recommended)

```bash
docker-compose up -d postgres
cp .env.example .env  # then edit
docker-compose up app
```

### 4. Or run locally

```bash
# Start PostgreSQL (Docker or local install)
# Initialize DB
python scripts/init_db.py

# Start the dashboard
uvicorn app.main:app --reload --port 8080
# Open: http://localhost:8080
```

## Content Calendar

The `content-calendar.csv` drives daily content generation.

| Column | Values |
|--------|--------|
| `date` | ISO date (YYYY-MM-DD) |
| `topic` | Free text topic description |
| `platform` | `linkedin`, `twitter`, `blog` |
| `content_pillar` | `AI fairness`, `regulatory updates`, `blockchain trust`, `case studies`, `behind the scenes` |

Edit the CSV and re-import:
```bash
curl -X POST "http://localhost:8080/api/calendar/import?overwrite=true"
```

## Manual Commands

```bash
# Run news scan manually
python scripts/run_news_scan.py

# Dry-run (no DB writes)
python scripts/run_news_scan.py --dry-run

# Generate content from today's calendar
python scripts/run_content_gen.py

# Generate for a specific date
python scripts/run_content_gen.py calendar --date 2026-03-05

# Generate a single piece manually
python scripts/run_content_gen.py manual \
  --topic "The EU AI Act compliance timeline for non-EU companies" \
  --platform linkedin \
  --pillar "regulatory updates"
```

## Cron Setup

```cron
# /etc/cron.d/auditchain-content-engine
0 6 * * * /path/to/.venv/bin/python /path/to/scripts/run_news_scan.py >> /var/log/auditchain-news.log 2>&1
0 7 * * * /path/to/.venv/bin/python /path/to/scripts/run_content_gen.py >> /var/log/auditchain-content.log 2>&1
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard HTML |
| GET | `/api/stats` | Dashboard stats |
| GET | `/api/content` | List content (filterable) |
| PATCH | `/api/content/{id}` | Edit content |
| POST | `/api/content/{id}/approve` | Approve for scheduling |
| POST | `/api/content/{id}/reject` | Reject with notes |
| POST | `/api/content/generate` | Manual generation |
| GET | `/api/news` | List news items |
| POST | `/api/news/scan` | Trigger news scan |
| GET | `/api/export` | Buffer-compatible JSON export |
| POST | `/api/export/buffer` | Push to Buffer API |
| GET | `/api/calendar` | List calendar entries |
| POST | `/api/calendar/import` | Import/re-import CSV |
| GET | `/api/scheduler/status` | Scheduler job status |
| GET | `/api/docs` | Interactive OpenAPI docs |

## Buffer Integration

Export approved content as Buffer-compatible JSON:
```bash
curl http://localhost:8080/api/export > buffer_export.json
```

Or push directly to Buffer (requires `BUFFER_ACCESS_TOKEN` in `.env`):
```bash
curl -X POST "http://localhost:8080/api/export/buffer" \
  -H "Content-Type: application/json" \
  -d '[1, 2, 3]'  # content IDs
```

## Content Pillars & Brand Voice

| Pillar | Focus |
|--------|-------|
| AI Fairness | Demographic parity, equalized odds, disparate impact; Global South context |
| Regulatory Updates | EU AI Act, OECD, India/Africa AI governance — practical implications |
| Blockchain Trust | Why NFT audit certificates matter; honest about limitations |
| Case Studies | Real-world audit findings; anonymized examples |
| Behind the Scenes | How SHAP works, audit pipeline internals |

**Brand voice**: Authoritative but accessible. Technical but not jargon-heavy. Global South perspective. Define terms on first use.

## RSS Feeds Monitored

- MIT Technology Review AI (`technologyreview.com/feed/`)
- TechCabal — African tech (`techcabal.com/feed/`)
- Inc42 — Indian startup/tech (`inc42.com/feed/`)
- OECD AI Policy Observatory (`oecd.ai/en/wonk/feed`)
- EU AI Act Watch (`artificialintelligenceact.eu/feed/`)

Add more feeds in `app/config.py` → `rss_feeds` dict.

## Tech Stack

- **Python 3.11+** with type hints throughout
- **FastAPI** — API + dashboard server
- **Anthropic SDK** — Claude `claude-sonnet-4-5-20250929` via streaming
- **SQLAlchemy 2.0 async** — ORM with asyncpg
- **APScheduler** — cron-style async task scheduling
- **feedparser + httpx** — async RSS fetching
- **Jinja2 + Bootstrap 5** — dashboard UI
- **PostgreSQL 15** — persistent storage
