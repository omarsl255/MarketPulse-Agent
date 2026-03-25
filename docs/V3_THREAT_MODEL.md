# V3 threat model (internal)

Short internal threat model for the RivalSense prototype as it moves toward V3 (deployment, alerts, RAG, agents, observability). It is not a formal security assessment; use it to prioritize controls during design and implementation.

## System context (relevant components)

| Component | Role |
|-----------|------|
| `collector.py` | Fetches configured URLs over HTTPS (`requests`) |
| `extractor.py` | Sends text to Gemini; structured output via Pydantic |
| `db.py` / SQLite | Stores events, snapshots, failures |
| `app.py` / Streamlit | Local or hosted dashboard over HTTP(S) |
| Future: alerts | Outbound webhooks (Slack/Teams/email) |
| Future: RAG | Vector store + retrieval into prompts |
| Future: deep agent | Tool use (browse, APIs, etc.) |

## Threats and mitigations

### 1. Server-side request forgery (SSRF) and scope creep

**Risk:** If URL lists become user-supplied or editable without review, the collector could be pointed at internal IPs, metadata endpoints, or `file:` URLs (depending on client configuration).

**Mitigations:**

- Keep an allowlist mindset for production targets; prefer fixed `config.yaml` (or equivalent) with review.
- Allow only `https:` (and explicitly chosen schemes); reject private/link-local ranges if any dynamic URL entry is introduced.
- Keep TLS verification enabled in `requests` (default); do not disable certificate checks for convenience.

### 2. Prompt injection via scraped content

**Risk:** Competitor-controlled pages can embed text intended to manipulate the model (ignore instructions, leak secrets, or mis-label events).

**Mitigations:**

- Continue strict structured output validation (Pydantic).
- Prefer visible text over raw HTML where possible; enforce `max_input_chars` and truncation policies.
- Harden system/developer prompts against following embedded instructions; treat page body as untrusted data.
- For RAG: retrieved chunks are also untrusted—same defenses apply.

### 3. Streamlit and dashboard exposure

**Risk:** Running Streamlit on `0.0.0.0` or exposing it without auth allows unauthorized access to competitive intelligence and stored snapshots.

**Mitigations:**

- Do not expose the prototype dashboard to the public internet without authentication (SSO/OIDC, reverse proxy, or managed hosting with auth).
- Use TLS at the edge; secure session configuration if using cookie-based auth.
- If multiple analysts need different access levels, plan RBAC with the deployment architecture (not Streamlit defaults alone).

### 4. Secrets and outbound integrations

**Risk:** `GOOGLE_API_KEY` or webhook URLs committed to git, logged in plain text, or shared in alert channels.

**Mitigations:**

- Use a secrets manager in deployed environments; rotate on suspicion of leak.
- Never log full API keys or webhook query strings; see [OBSERVABILITY_REDACTION.md](OBSERVABILITY_REDACTION.md).
- Scope Slack/Teams channels narrowly; avoid pasting full raw page content into wide-audience channels.

### 5. Deep agent / tool abuse

**Risk:** An agent with browsing or HTTP tools could be tricked into calling internal services or exfiltrating data.

**Mitigations:**

- Tool allowlists, URL policies, and per-step audit logs for external calls.
- Rate limits and maximum tool-call counts per task.
- Run agents with minimal network privileges where possible.

### 6. Data store and scaling

**Risk:** SQLite on shared/network filesystems can corrupt under concurrent writers; backup gaps lose audit history.

**Mitigations:**

- Avoid multi-writer NFS-style mounts for SQLite; migrate to Postgres (e.g. with pgvector) before horizontal scale.
- Document backup/restore for the chosen database.

### 7. Supply chain

**Risk:** Vulnerable dependencies.

**Mitigations:**

- Pin or constrain versions in `requirements.txt`; run periodic CVE scanning and upgrades.

## References

- [README V3 roadmap](../README.md#v3-roadmap-future)
- [TECH_STACK.md](TECH_STACK.md)
- [OBSERVABILITY_REDACTION.md](OBSERVABILITY_REDACTION.md)
