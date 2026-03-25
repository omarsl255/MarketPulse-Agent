# RivalSense — Competitor Early-Warning Intelligence Agent (V3)

A multi-competitor analytics agent that proactively monitors industrial automation rivals (Siemens, Schneider Electric, Rockwell Automation) by analyzing unconventional "weak signals" on the web — beyond press releases and business reports.

> **Perspective:** ABB  
> **Targets:** Siemens, Schneider Electric, Rockwell Automation  
> **LLM Backend:** Google Gemini (`gemini-2.5-flash`)  
> **Version:** 0.4.0 (`V3`)

---

## Current Project Status: V3 Working Prototype

This version adds deployment, authentication, alerting, observability, cross-signal correlation, analyst review workflows, and a governed agent layer on top of the V2 extraction pipeline.

### Implemented in V3
1.  **Collect** raw web content from competitor URLs with retry logic and URL safety guardrails.
2.  **Detect changes** with SHA-256 snapshots and skip unchanged pages.
3.  **Extract** structured events using signal-specific Gemini prompts.
4.  **Calibrate** confidence scores with a second-pass LLM review.
5.  **Correlate** events across competitors and signal types using keyword-theme heuristics.
6.  **Alert** high-confidence events to Slack, Teams, email, or log (secrets from env only).
7.  **Store** events, snapshots, failures, runs, alerts, reviews, correlations, and budget usage in SQLite.
8.  **Review** events through an analyst queue with confirm/dismiss/escalate workflow.
9.  **Observe** pipeline stages with redacted structured tracing (no secrets in traces).
10. **Schedule** recurring runs via APScheduler with run metadata tracking.
11. **Display** results in a Streamlit dashboard with tabs for Radar, Review Queue, Correlations, and Operations.
12. **Deploy** via Docker with separate dashboard, scheduler, and one-shot pipeline services.
13. **Authenticate** dashboard access via reverse proxy headers or basic password.
14. **Evaluate** extraction quality with a golden-set harness.
15. **Govern** agent workflows with tool allowlists, audit logs, step limits, and approval gates.

### Architecture
```
config.yaml → config_loader.py (URL validation, safety checks)
                    ↓
collector.py → differ.py → extractor.py → correlator.py → notifier.py → db.py → app.py
  (Scrape)      (Diff)      (LLM/Gemini)   (Heuristic)    (Alerts)     (SQLite) (Dashboard)
                              ↑                                           ↑
                         prompts/*.txt                              observability.py
                       (signal-specific)                            (redacted tracing)
                                                                         ↑
                                                                    agent.py
                                                                  (governed tools)
```

### Files
| File | Purpose |
|---|---|
| `config.yaml` | Central config: competitors, URLs, LLM, alerts, observability, auth, budget, retention |
| `config_loader.py` | YAML loading + `.env` secrets + URL validation guardrails |
| `schema.py` | Pydantic models: Event, Snapshot, Source, Profile, Theme, Failure, Run, Alert, Review, Correlation, Budget |
| `collector.py` | Web scraper with exponential backoff retries |
| `differ.py` | SHA-256 change detection + `difflib` diff summaries |
| `extractor.py` | Multi-event LLM extraction + confidence calibration |
| `correlator.py` | Cross-signal correlation engine (keyword-theme heuristics) |
| `notifier.py` | Alert routing: log, Slack, Teams, email (secrets from environment) |
| `observability.py` | Structured redacted tracing (no secrets, truncated text, hashed URLs) |
| `auth.py` | Authentication boundary: none, reverse_proxy, or basic password |
| `agent.py` | Governed agent layer: tool allowlists, audit logs, step limits, approval gates |
| `evaluator.py` | Golden-set evaluation harness for extraction quality |
| `prompts/` | Templates for `developer_api`, `github`, `open_source`, `corporate`, `careers`, `press`, `events`, `generic`, plus forward-looking `academic_sponsorship`, `patent_outer_citation`, `hyperlocal_zoning` |
| `db.py` | SQLite: events, snapshots, failures, runs, alerts, reviews, correlations, budget |
| `main.py` | Pipeline orchestrator: collect → diff → extract → correlate → alert → store |
| `scheduler.py` | APScheduler-based recurring execution |
| `app.py` | Streamlit dashboard: Radar, Review Queue, Correlations, Operations tabs |
| `tests/` | pytest tests for all modules (mocked, no API calls needed) |
| `golden_sets/` | Labeled evaluation data for extraction quality |
| `Dockerfile` | Container image for dashboard, pipeline, or scheduler |
| `docker-compose.yml` | Multi-service deployment: dashboard + scheduler + one-shot pipeline |
| `docs/TECH_STACK.md` | Tech stack reference |
| `docs/V3_THREAT_MODEL.md` | Internal threat model |
| `docs/OBSERVABILITY_REDACTION.md` | Redaction policy for traces and logs |
| `docs/WEAK_SIGNALS_AGENTIC_WORKFLOWS.md` | Agentic workflow spec for all 5 strategic signals |
| `docs/signals/` | One markdown file per strategic weak signal (idea, goal, workflow, example URLs) |

---

## Quick Start

```powershell
# 1. Activate environment
cd "c:\Users\z0057hdz\Desktop\Ai agent\prototype"
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Gemini API key (or create a .env file from .env.example)
$env:GOOGLE_API_KEY="your-api-key-here"

# 4. Run the extraction pipeline
python main.py

# Without GOOGLE_API_KEY, the pipeline creates mock events so you can still test the flow.

# 5. Launch the dashboard
streamlit run app.py

# 6. (Optional) Start scheduled runs
python scheduler.py

# 7. Run tests
pytest tests/ -v
```

### Docker deployment

```bash
# Build and start dashboard + scheduler
docker compose up -d

# Run a one-shot pipeline
docker compose run --rm pipeline

# Dashboard available at http://localhost:8501
```

---

## Signal Coverage

The codebase supports multiple source categories through `config.yaml`, the collector, and prompt templates.

**Agentic workflow spec (all 5 strategic weak signals):** see [`docs/WEAK_SIGNALS_AGENTIC_WORKFLOWS.md`](docs/WEAK_SIGNALS_AGENTIC_WORKFLOWS.md).

**Per-signal quick docs:** see:
- [`docs/signals/niche_driver_protocol_update_spikes.md`](docs/signals/niche_driver_protocol_update_spikes.md)
- [`docs/signals/academic_sponsorship_trajectory.md`](docs/signals/academic_sponsorship_trajectory.md)
- [`docs/signals/patent_citations_outer_industries.md`](docs/signals/patent_citations_outer_industries.md)
- [`docs/signals/hyperlocal_factory_town_intelligence.md`](docs/signals/hyperlocal_factory_town_intelligence.md)
- [`docs/signals/developer_api_subdomain_evolution.md`](docs/signals/developer_api_subdomain_evolution.md)
- [`docs/signals/non_live_signals.md`](docs/signals/non_live_signals.md) (combined view for framework-level, non-live signals)

### Best-Supported Today
- **Developer API / developer portal monitoring** is the most complete path with dedicated prompt support and golden-set evaluation data.
- **GitHub / open-source / corporate / careers / press / events** sources have prompt coverage or generic fallback support.

### Partial / Framework-Level Support
- **Academic sponsorship**, **patent outer citation**, and **hyperlocal zoning** have prompt files and agentic workflow specs but are not yet wired as live URL targets in `config.yaml`.

## The 5 Strategic "Weak Signals" (Interview Framework)

| # | Signal | Data Source | Time Horizon |
|---|---|---|---|
| 1 | **Niche Driver & Protocol Update Spikes** | GitHub repos, industrial protocol forums | 6–12 months ahead |
| 2 | **Academic Sponsorship Trajectory** | University "Future Lab" funding, PhD fellowships | 5–10 years ahead |
| 3 | **Patent Citations from "Outer" Industries** | Patent databases (cross-sector citations) | 2–5 years ahead |
| 4 | **Hyper-Local "Factory Town" Intelligence** | Local German newspapers, municipal zoning filings | 3–12 months ahead |
| 5 | **Developer API & Subdomain Evolution** | Developer portals, CT logs, API catalogs | 3–6 months ahead |

---

## V3 Improvements Over V2

| Area | V2 | V3 |
|---|---|---|
| **Deployment** | Local only | Docker + docker-compose |
| **Authentication** | None | Reverse proxy or basic password |
| **Alerting** | None | Slack, Teams, email, log (secrets from env) |
| **Observability** | Print logging | Structured redacted tracing |
| **Correlation** | None | Cross-signal keyword-theme heuristics |
| **Analyst Workflow** | View only | Confirm/dismiss/escalate review queue |
| **Agent Layer** | None | Governed tools with allowlists, audit logs, approval gates |
| **Evaluation** | None | Golden-set harness for extraction quality |
| **Data Model** | 3 tables | 8 tables (events, snapshots, failures, runs, alerts, reviews, correlations, budget) |
| **Config Safety** | No validation | URL scheme validation, private IP blocking, duplicate detection |
| **Budget Control** | None | Per-run token and call limits |
| **Retention** | None | Configurable retention windows with automatic cleanup |
| **Signal Coverage** | No events prompt | Events prompt + expanded Rockwell config |

---

## V2 Improvements Over V1

| Area | V1 | V2 |
|---|---|---|
| **Targets** | Single URL (Siemens only) | Multi-URL, multi-competitor via `config.yaml` |
| **Change Detection** | None | SHA-256 diffing — only processes changed pages |
| **Extraction** | Single event per page | Multiple events per page (JSON array) |
| **Prompts** | Single generic prompt | Signal-specific prompt templates (`prompts/`) |
| **Confidence** | LLM always returns high | Two-pass calibration with rubric |
| **Scheduling** | Manual only | APScheduler with configurable interval |
| **Error Handling** | Basic try/except | Exponential backoff retries + dead-letter queue |
| **Data Model** | Flat `CompetitorEvent` | Rich model with snapshots, failures, run metadata |
| **Security** | API key in env var | `python-dotenv` + `.env` file + `.env.example` |

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.12+ |
| LLM | Google Gemini (`gemini-2.5-flash`) via `langchain_google_genai` |
| Orchestration | LangChain |
| Web Scraping | `requests` + `BeautifulSoup4` |
| Change Detection | SHA-256 + `difflib` |
| Database | SQLite (WAL mode) |
| Dashboard | Streamlit |
| Charts | Altair |
| Scheduling | APScheduler |
| Config | YAML + Pydantic |
| Secrets | `python-dotenv` + environment variables |
| Testing | pytest (mocked) |
| Container | Docker + docker-compose |

---

## Future Directions

- **RAG / vector retrieval** — ChromaDB/pgvector for semantic search across evidence
- **Deeper agent workflows** — Multi-step investigation with tool-calling LLM agents
- **Postgres migration** — For concurrent access and horizontal scale
- **Langfuse/LangSmith** — Pluggable observability backend (redaction layer ready)
- **SSO/OIDC** — Production authentication
- **API layer** — Authenticated HTTP API for programmatic access
