# 📡 Competitor Early-Warning Intelligence Agent

A multi-competitor analytics agent that proactively monitors industrial automation rivals (Siemens, ABB, Schneider Electric, Rockwell Automation) by analyzing unconventional "weak signals" on the web — beyond press releases and business reports.

> **Perspective:** ABB  
> **Primary Target (V1):** Siemens Digital Industries  
> **LLM Backend:** Google Gemini (`gemini-2.5-flash`)

---

## Current Project Status: ✅ V1 Prototype — Functional

The end-to-end pipeline is working. It can:
1.  **Collect** raw web content from a target URL (e.g., `developer.siemens.com`).
2.  **Extract** a structured strategic event using Gemini LLM.
3.  **Store** the event in a local SQLite database.
4.  **Display** results in a Streamlit dashboard with confidence scoring.

### Architecture
```
collector.py → extractor.py → db.py → app.py (Streamlit)
   (Scrape)      (LLM/Gemini)    (SQLite)    (Dashboard)
```

### Files
| File | Purpose |
|---|---|
| `schema.py` | Pydantic data model for `CompetitorEvent` |
| `collector.py` | Web scraper using `requests` + `BeautifulSoup` |
| `extractor.py` | LangChain + Gemini LLM extraction chain |
| `db.py` | SQLite database initialization and CRUD |
| `main.py` | Pipeline orchestrator (collect → extract → store) |
| `app.py` | Streamlit dashboard UI |

---

## Quick Start

```powershell
# 1. Activate environment
cd "c:\Users\z0057hdz\Desktop\Ai agent\prototype"
.\venv\Scripts\Activate.ps1

# 2. Set your Gemini API key
$env:GOOGLE_API_KEY="your-api-key-here"

# 3. Run the extraction pipeline
python main.py

# 4. Launch the dashboard
streamlit run app.py
```

---

## The 5 Strategic "Weak Signals" (Interview Framework)

| # | Signal | Data Source | Time Horizon |
|---|---|---|---|
| 1 | **Niche Driver & Protocol Update Spikes** | GitHub repos, industrial protocol forums | 6–12 months ahead |
| 2 | **Academic Sponsorship Trajectory** | University "Future Lab" funding, PhD fellowships | 5–10 years ahead |
| 3 | **Patent Citations from "Outer" Industries** | Patent databases (cross-sector citations) | 2–5 years ahead |
| 4 | **Hyper-Local "Factory Town" Intelligence** | Local German newspapers, municipal zoning filings | 3–12 months ahead |
| 5 | **Developer API & Subdomain Evolution** ✅ | Developer portals, CT logs, API catalogs | 3–6 months ahead |

> Signal 5 is the one currently implemented in this V1 prototype.

### Additional Signals (Reference List)
- Job Posting "Cluster" Shifts (tech stack changes by geography)
- Local Energy Grid Requests (power upgrades near factories)
- Shipping Manifest Anomalies (rare earth / semiconductor imports)
- Employee Sentiment Volatility (Glassdoor/Kununu for specific divisions)
- Standardization Body Activity (OPC UA FX, 6G voting patterns)
- Domain Name / Subdomain Registrations

---

## What's Missing (V2 Roadmap)

### 🔴 High Priority
- [ ] **Multi-URL target list** — Currently only scrapes one URL. Should cover API catalogs, GitHub orgs, partner directories, and job boards.
- [ ] **Change detection** — No diffing between runs. The agent should compare today's scrape to yesterday's and only flag *new* changes.
- [ ] **Scheduling** — Pipeline runs manually. Needs a scheduler (e.g., `APScheduler`, `cron`, or `Prefect`) for daily automated runs.
- [ ] **Multi-competitor support** — Schema supports it, but `main.py` only targets Siemens. Add ABB, Schneider, Rockwell URLs.

### 🟡 Medium Priority
- [ ] **Vector storage (RAG)** — Add ChromaDB or pgvector to enable semantic search over collected evidence (e.g., "What changed in industrial AI this month?").
- [ ] **Multi-event extraction** — Gemini sometimes finds multiple signals per page. Extractor currently forces a single event; should handle lists.
- [ ] **Alert routing** — Send high-confidence alerts to Slack, Teams, or email instead of only showing them on the dashboard.
- [ ] **Confidence calibration** — LLM always returns high confidence. Add heuristics or a second-pass validation step.

### 🟢 Nice to Have
- [ ] **Deep Agent layer** — Add a LangChain Deep Agent for analyst-facing investigation workflows (e.g., "Compare Siemens vs ABB edge computing moves").
- [ ] **Cross-signal correlation** — Detect when multiple weak signals align (e.g., new API + hiring spike + patent filing = high-confidence strategic move).
- [ ] **Historical trend charts** — Dashboard should show signal timelines and competitor comparison graphs.
- [ ] **Observability** — Add Langfuse or LangSmith for prompt tracing, token usage, and evaluation tracking.
- [ ] **Authentication & deployment** — Containerize with Docker, add user auth, deploy to cloud.

---

## What to Improve

| Area | Current State | Improvement |
|---|---|---|
| **Error handling** | Basic try/except | Add retries, structured logging, dead-letter queue for failed extractions |
| **Prompt engineering** | Single generic prompt | Create signal-specific prompts per weak signal type |
| **Data model** | Flat `CompetitorEvent` | Add `SignalSource`, `CompetitorProfile`, and `StrategicTheme` models |
| **Testing** | Manual only | Add `pytest` unit tests for collector, extractor, and db modules |
| **Security** | API key in env var | Use a secrets manager; never hardcode keys |
| **Dashboard UX** | Functional but basic | Add charts, timelines, competitor comparison views, and dark mode |

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.14 |
| LLM | Google Gemini (`gemini-2.5-flash`) via `langchain_google_genai` |
| Orchestration | LangChain |
| Web Scraping | `requests` + `BeautifulSoup4` |
| Database | SQLite |
| Data Validation | Pydantic |
| Dashboard | Streamlit |

---

## License
Internal prototype — not for distribution.
