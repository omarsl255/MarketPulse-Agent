# 📡 Competitor Early-Warning Intelligence Agent — V2

A multi-competitor analytics agent that proactively monitors industrial automation rivals (Siemens, Schneider Electric, Rockwell Automation) by analyzing unconventional "weak signals" on the web — beyond press releases and business reports.

> **Perspective:** ABB  
> **Targets:** Siemens, Schneider Electric, Rockwell Automation  
> **LLM Backend:** Google Gemini (`gemini-2.5-flash`)  
> **Version:** 0.3.0 (`V2` prototype)

---

## Current Project Status: ✅ V2 Working Prototype

This repository is currently a working **internal prototype** of the multi-competitor intelligence pipeline. The core end-to-end flow is implemented and wired together, but signal coverage and analyst workflows are still uneven across source types.

### Implemented Today
1.  **Collect** raw web content from competitor URLs with retry logic.
2.  **Detect changes** with SHA-256 snapshots and skip unchanged pages.
3.  **Extract** one or more structured events from changed pages using Gemini prompts.
4.  **Calibrate** confidence scores with a second-pass LLM review.
5.  **Store** events, snapshots, and failed extractions in SQLite.
6.  **Schedule** recurring runs via APScheduler.
7.  **Display** results in a Streamlit dashboard with filtering and charts.

### Current Boundaries
- The project is **not** production-ready yet: there is no deployment, auth layer, alert routing, or observability stack in the current version.
- Prompt support exists for several source categories, but not every strategic signal has a fully specialized workflow yet.
- If `GOOGLE_API_KEY` is not set, the pipeline still runs in a limited mock mode so the ingestion and dashboard flow can be exercised without live LLM extraction.

### Architecture
```
config.yaml → config_loader.py
                    ↓
collector.py → differ.py → extractor.py → db.py → app.py (Streamlit)
  (Scrape)      (Diff)      (LLM/Gemini)   (SQLite)  (Dashboard)
                              ↑
                         prompts/*.txt
                       (signal-specific)
```

### Files
| File | Purpose |
|---|---|
| `config.yaml` | Central config: competitors, URLs, LLM settings, schedule |
| `config_loader.py` | YAML config loading + `.env` secrets management |
| `schema.py` | Pydantic models: `CompetitorEvent`, `ContentSnapshot`, `SignalSource`, `CompetitorProfile`, `StrategicTheme`, `FailedExtraction` |
| `collector.py` | Web scraper with exponential backoff retries |
| `differ.py` | SHA-256 change detection + `difflib` diff summaries |
| `extractor.py` | Multi-event LLM extraction + confidence calibration |
| `prompts/` | Templates for `developer_api`, `github`, `open_source`, `corporate`, `careers`, `press`, `generic`, plus forward-looking `academic_sponsorship`, `patent_outer_citation`, `hyperlocal_zoning` (use matching `signal_type` in `config.yaml`) |
| `db.py` | SQLite: events, snapshots, dead-letter queue |
| `main.py` | Pipeline orchestrator (collect → diff → extract → store) |
| `scheduler.py` | APScheduler-based recurring execution |
| `app.py` | Streamlit dashboard with charts and filtering |
| `tests/` | 41 pytest tests (all mocked, no API calls needed) |
| `docs/TECH_STACK.md` | Tech stack: libraries, LLM model, runtime processes, and external services |
| `docs/V3_THREAT_MODEL.md` | Short internal threat model for V3 (SSRF, prompt injection, Streamlit exposure, ops) |
| `docs/OBSERVABILITY_REDACTION.md` | Redaction policy before Langfuse/LangSmith in prod-like environments |

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

---

## Signal Coverage

The codebase supports multiple source categories through `config.yaml`, the collector, and prompt templates. In practice, maturity varies by signal family.

**Agentic workflow spec (all 5 strategic weak signals):** see [`docs/WEAK_SIGNALS_AGENTIC_WORKFLOWS.md`](docs/WEAK_SIGNALS_AGENTIC_WORKFLOWS.md).

### Best-Supported Today
- **Developer API / developer portal monitoring** is the most complete path today and has dedicated prompt support.
- **GitHub / open-source / corporate / careers / press** sources also have prompt coverage or generic fallback support in the current prototype.

### Partial / Framework-Level Support
- Additional strategic signal ideas are documented below, but several of them are still conceptual research directions rather than deeply implemented workflows.

## The 5 Strategic "Weak Signals" (Interview Framework)

| # | Signal | Data Source | Time Horizon |
|---|---|---|---|
| 1 | **Niche Driver & Protocol Update Spikes** | GitHub repos, industrial protocol forums | 6–12 months ahead |
| 2 | **Academic Sponsorship Trajectory** | University "Future Lab" funding, PhD fellowships | 5–10 years ahead |
| 3 | **Patent Citations from "Outer" Industries** | Patent databases (cross-sector citations) | 2–5 years ahead |
| 4 | **Hyper-Local "Factory Town" Intelligence** | Local German newspapers, municipal zoning filings | 3–12 months ahead |
| 5 | **Developer API & Subdomain Evolution** ✅ | Developer portals, CT logs, API catalogs | 3–6 months ahead |

> Signal 5 is the strongest implemented workflow in the current prototype.
> Signal 1 has dedicated prompt support, while the remaining signal families are still broader prototype coverage areas rather than deeply specialized pipelines.

### Additional Signals (Reference List)
- Job Posting "Cluster" Shifts (tech stack changes by geography)
- Local Energy Grid Requests (power upgrades near factories)
- Shipping Manifest Anomalies (rare earth / semiconductor imports)
- Employee Sentiment Volatility (Glassdoor/Kununu for specific divisions)
- Standardization Body Activity (OPC UA FX, 6G voting patterns)
- Domain Name / Subdomain Registrations

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
| **Data Model** | Flat `CompetitorEvent` | 6 models: Event, Snapshot, Source, Profile, Theme, Failure |
| **Security** | API key in env var | `python-dotenv` + `.env` file + `.env.example` |
| **Dashboard** | Functional but basic | Charts, timelines, confidence histogram, NEW badges, dark mode |
| **Testing** | Manual only | 41 pytest tests (all mocked) |
| **Logging** | `print()` statements | Structured `logging` module |

---

## V3 Roadmap (Future)

**Recommended sequence:** Implement **authentication, safe deployment, and secret handling for outbound integrations (alerts)** before scaling **deep agents** and **broad RAG**—tool-calling and retrieval increase operational and security risk. **Observability** is useful early, but only after adopting the [observability redaction policy](docs/OBSERVABILITY_REDACTION.md). For risks and mitigations, see the [V3 threat model](docs/V3_THREAT_MODEL.md).

### Phase 1 — Foundation (ship first)

- [ ] **Authentication & deployment** — Docker + cloud deployment + explicit user auth (e.g. SSO/OIDC or reverse proxy in front of Streamlit); do not expose the dashboard to the public internet without auth
- [ ] **Alert routing** — Slack/Teams/email for high-confidence alerts; store webhook URLs and tokens in a secrets manager, rotate on leak, least-privilege channels
- [ ] **Observability** — Langfuse/LangSmith for prompt tracing and token tracking; apply [redaction rules](docs/OBSERVABILITY_REDACTION.md) before prod-like or multi-user environments

### Phase 2 — Intelligence depth

- [ ] **Broader signal specialization** — Move more source categories from generic/fallback prompting into dedicated extraction workflows
- [ ] **Cross-signal correlation** — Detect when multiple signals align
- [ ] **Vector storage (RAG)** — ChromaDB/pgvector for semantic search across evidence; pair with access control and retrieval-aware defenses (see threat model)

### Phase 3 — Agentic expansion (after Phase 1)

- [ ] **Deep Agent layer** — LangChain agent for analyst investigation workflows; tool allowlists, URL policies, and audit logging for every external call

### Cross-cutting (throughout V3)

- [ ] **Data lifecycle & compliance** — Retention for snapshots/events, export/delete where needed, classification of competitive intel vs. PII (e.g. careers content)
- [ ] **Config guardrails** — Validate/review `config.yaml` URL lists (HTTPS-only mindset, avoid accidental internal or `file:` targets as config becomes more dynamic)
- [ ] **Evaluation harness** — Golden-set regression tests for extraction when prompts or models change
- [ ] **Cost & quota governance** — Per-run/per-competitor budgets; caps on input size and on agent tool-call loops
- [ ] **Human-in-the-loop** — Optional analyst confirmation before alerts or high-impact exports
- [ ] **Backup & recovery** — SQLite backup discipline; automated DB backups if moving to Postgres/pgvector
- [ ] **Optional API layer** — Small authenticated HTTP API if multiple clients need data beyond Streamlit

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
| Dashboard | Streamlit + Altair |
| Scheduling | APScheduler |
| Config | YAML + `python-dotenv` |
| Testing | pytest |

---

## License
Internal prototype — not for distribution.
