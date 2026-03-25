# Signal 1 — Niche Driver & Protocol Update Spikes

## Idea

Detect early technical movement in low-level software (drivers, protocol adapters, embedded SDKs) before those changes appear in polished product marketing. Fast changes in repositories and protocol discussions can reveal platform bets and interoperability direction.

## Goal

Identify protocol and driver changes early enough for ABB to:
- anticipate ecosystem shifts (for example OPC UA, MQTT, TSN, Profinet)
- spot compatibility or lock-in risks
- prioritize competitive response in product and partner strategy

## Workflow

1. **Plan targets**: maintain competitor mappings to GitHub orgs, key repos, and protocol-related sources.
2. **Collect**: pull release notes, commit metadata, issues, and relevant public discussion pages.
3. **Detect changes**: hash and diff content so unchanged pages are skipped.
4. **Extract**: identify protocol entities, magnitude of change, and potential strategic meaning.
5. **Verify**: downgrade weak claims and keep only evidence-backed events.
6. **Store and surface**: persist structured events for dashboard and analyst review.

## Example URLs

These are representative public examples and starting points, not guaranteed live integrations.

- `https://github.com/siemens`
- `https://github.com/schneider-electric`
- `https://github.com/rockwellautomation`
- `https://github.com/siemens?tab=repositories`
- `https://github.com/schneider-electric?tab=repositories`
- `https://github.com/rockwellautomation?tab=repositories`
