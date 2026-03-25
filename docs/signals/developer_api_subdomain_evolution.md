# Signal 5 — Developer API & Subdomain Evolution

## Idea

Monitor developer-facing technical surfaces such as API docs, changelogs, SDK references, and public subdomain activity. These changes often show platform direction and partner integration strategy before full product announcements.

## Goal

Help ABB detect short-horizon platform moves by competitors to:
- identify new endpoint families, version changes, and deprecation patterns
- anticipate partner ecosystem direction and integration impact
- surface evidence-backed early warnings for product and GTM planning

## Workflow

1. **Plan targets**: maintain competitor developer domains, docs paths, and high-value API URLs.
2. **Collect**: fetch portal pages, OpenAPI/AsyncAPI specs (when public), and domain-related signals.
3. **Detect changes**: diff docs/spec content and track newly observed technical surfaces.
4. **Extract**: capture concrete API or SDK changes and likely strategic implications.
5. **Verify**: separate true deprecations from experiments and downgrade noisy host-only claims.
6. **Store and surface**: persist structured events and route high-confidence items to analysts.

## Example URLs

These are representative public examples and starting points, not guaranteed live integrations.

- `https://developer.siemens.com/`
- `https://developer.se.com/`
- `https://developer.rockwellautomation.com/`
- `https://new.siemens.com/global/en/products/services/digital-enterprise-services/api.html`
- `https://www.se.com/ww/en/work/support/`
- `https://crt.sh/?q=siemens.com`
