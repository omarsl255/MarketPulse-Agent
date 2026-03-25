# Observability redaction policy

Use this policy **before** enabling Langfuse, LangSmith, or similar tracing in shared, production-like, or multi-tenant environments. Traces often contain prompts, completions, and metadata that qualify as sensitive internal data or personal data from scraped sources (e.g. job postings).

## Goals

1. **Prevent secret leakage** — API keys, webhook tokens, and OAuth material must never appear in trace payloads or logs.
2. **Limit competitive and personal data exposure** — Treat full page text, URLs with sensitive query parameters, and analyst notes as confidential unless explicitly approved for export to a third-party observability vendor.
3. **Keep traces useful** — Retain enough structure (IDs, hashes, timings, token counts, error classes) to debug quality and cost.

## Default rules

| Data class | In traces / hosted observability | In local-only debug logs (short-lived) |
|------------|-----------------------------------|----------------------------------------|
| `GOOGLE_API_KEY` and other secrets | **Never** | **Never** |
| Full webhook URLs (Slack/Teams) | **Never** | Avoid; log “webhook configured: yes/no” only |
| Full user prompts / raw scraped text | **Avoid** unless redacted/summarized | Optional for single-developer machines; delete aggressively |
| Model completions | **Avoid** full text in vendor cloud if policy requires; prefer hashes or truncated excerpts | Same discipline as prompts |
| Stable identifiers | **Yes** — event IDs, snapshot IDs, UUIDs, run IDs | Yes |
| URL | **Prefer** canonical URL or **hash** of URL; strip query strings unless required | Prefer stripped/hashed |
| Token counts, latency, model name | **Yes** | Yes |
| Error messages | **Yes** if scrubbed of secrets and PII | Yes |

## Implementation checklist (when wiring Langfuse / LangSmith)

1. **Configure clients** to use environment-specific projects (e.g. `rival-sense-dev` vs `rival-sense-prod`) and restrict project access to people who may see competitive intelligence.
2. **Wrap or filter** span inputs/outputs: strip keys matching `*API_KEY*`, `*SECRET*`, `*TOKEN*`, `*WEBHOOK*`, or known env var names before send.
3. **Truncate or hash** long text fields: e.g. first N characters + SHA-256 of full body for correlation without storing full body in the vendor.
4. **Disable** full prompt capture in vendor settings if the product supports a “metadata only” or “sampling” mode for production.
5. **Retention** — Align trace TTL with internal data retention policy; shorter is better for sensitive workloads.
6. **Subprocessors** — Ensure observability vendor choice is approved under your organization’s AI and vendor risk processes.

## Relationship to the threat model

Prompt and completion bodies in a third-party system are an **additional disclosure surface**. This policy complements [V3_THREAT_MODEL.md](V3_THREAT_MODEL.md) (prompt injection, Streamlit exposure, secrets).

## References

- [README V3 roadmap](../README.md#v3-roadmap-future)
- [TECH_STACK.md](TECH_STACK.md)
