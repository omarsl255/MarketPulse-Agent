# Non-Live Signals (Framework-Level)

This file groups the strategic signals that are currently defined in the framework but not yet wired as live URL targets in `config.yaml`.

## Signal 2 — Academic Sponsorship Trajectory

### Idea

Track long-horizon R&D direction through public university partnerships, sponsored labs, fellowships, and research program announcements.

### Goal

Detect early research positioning by competitors to anticipate talent and capability direction.

### Workflow

1. Plan a watchlist of universities, labs, grants, and keywords.
2. Collect public university and corporate research announcements.
3. Detect meaningful changes (new or materially updated announcements).
4. Extract entities, topics, timeline, and geography.
5. Verify with primary-source preference and confidence checks.
6. Store and surface events for analyst review.

### Example URLs

- `https://new.siemens.com/global/en/company/research.html`
- `https://www.se.com/ww/en/work/company/innovation/`
- `https://www.rockwellautomation.com/en-us/company/news.html`
- `https://cordis.europa.eu/projects/en`

## Signal 3 — Patent Citations from Outer Industries

### Idea

Identify competitor patents citing prior art from outside core industrial automation to reveal adjacent capability moves.

### Goal

Detect cross-industry technology direction early and prioritize deeper scouting where signals are strongest.

### Workflow

1. Plan assignee profiles and outer-sector filters.
2. Collect public patent filings and citation metadata.
3. Detect new cross-sector citation edges.
4. Extract focal patent, cited patent, sector distance, and implications.
5. Verify assignee mapping and metadata quality.
6. Store and surface events with stable public patent links.

### Example URLs

- `https://patentscope.wipo.int/search/en/search.jsf`
- `https://worldwide.espacenet.com/`
- `https://patents.google.com/`
- `https://developer.uspto.gov/`

## Signal 4 — Hyper-Local Factory Town Intelligence

### Idea

Use municipal zoning and permit records plus local reporting to catch site-level capacity and footprint changes earlier than national press.

### Goal

Identify near-term operational moves by competitors and improve regional competitive readiness.

### Workflow

1. Plan a geo watchlist of known sites, towns, and local keywords.
2. Collect local news and municipal planning or permit publications.
3. Detect new filings or articles and cluster duplicates.
4. Extract location, action type, and competitor linkage evidence.
5. Verify location/entity certainty before high-confidence claims.
6. Store and surface events for analyst review.

### Example URLs

- `https://www.bauleitplanung.de/`
- `https://www.muenchen.de/rathaus/Stadtverwaltung/Referat-fuer-Stadtplanung-und-Bauordnung/Bauleitplanung.html`
- `https://www.stuttgarter-zeitung.de/`
- `https://www.rnz.de/`
