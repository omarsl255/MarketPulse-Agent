# Signal 4 — Hyper-Local Factory Town Intelligence

## Idea

Use hyper-local public evidence such as municipal zoning changes, permit filings, and local newspaper reporting to detect site-level expansion or footprint shifts earlier than national corporate press.

## Goal

Allow ABB to identify near-term operational moves by competitors to:
- detect likely capacity changes and local investment signals
- monitor geographic expansion and logistics shifts
- improve regional readiness for competitive response

## Workflow

1. **Plan targets**: build a geo watchlist of known competitor sites, towns, and local keywords.
2. **Collect**: fetch local news pages, municipal planning notices, and public permit publications.
3. **Detect changes**: isolate new filings/articles and cluster duplicates across local outlets.
4. **Extract**: capture location, action type (permit, zoning, capex hint), and competitor linkage.
5. **Verify**: require strong location or entity evidence for high-confidence claims.
6. **Store and surface**: persist structured events for analyst review and trend tracking.

## Example URLs

These are representative public examples and starting points, not guaranteed live integrations.

- `https://www.bund.de/EN/Service/Service_node.html`
- `https://www.bauleitplanung.de/`
- `https://www.muenchen.de/rathaus/Stadtverwaltung/Referat-fuer-Stadtplanung-und-Bauordnung/Bauleitplanung.html`
- `https://www.stuttgarter-zeitung.de/`
- `https://www.rnz.de/`
- `https://www.handelsblatt.com/unternehmen/industrie/`
