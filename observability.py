"""
observability.py — Structured, redacted observability for V3.
Wraps pipeline stages with trace-safe metadata: run IDs, latency,
token counts, hashes, and scrubbed error messages.
Never emits full secrets, raw page text, or full webhook URLs.
"""

import re
import time
import logging
import hashlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger("observability")

_SECRET_PATTERNS = re.compile(
    r"(API_KEY|SECRET|TOKEN|WEBHOOK|PASSWORD|CREDENTIAL)",
    re.IGNORECASE,
)


@dataclass
class SpanRecord:
    """A single trace span emitted by the observability layer."""
    span_id: str = ""
    run_id: str = ""
    stage: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_ms: float = 0.0
    status: str = "ok"
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_class: str = ""
    error_message: str = ""


def redact_secret_values(text: str) -> str:
    """Replace values that look like secrets with [REDACTED]."""
    redacted = re.sub(
        r"(?i)(\w*(?:api[_-]?key|secret|token|webhook|password)\w*)\s*[=:]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )
    return redacted


def strip_url_query(url: str) -> str:
    """Strip query parameters from a URL for safe logging."""
    try:
        parsed = urlparse(url)
        clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        return clean
    except Exception:
        return "[unparseable-url]"


def hash_url(url: str) -> str:
    """Return a truncated SHA-256 of the URL for correlation without exposing full path."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def truncate_text(text: str, max_chars: int = 200) -> str:
    """Truncate text for trace payloads, appending hash for correlation."""
    if len(text) <= max_chars:
        return text
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return text[:max_chars] + f"...[truncated, sha256={h}]"


def scrub_error(error_msg: str) -> str:
    """Remove secrets from error messages before tracing."""
    return redact_secret_values(str(error_msg)[:500])


def safe_metadata(
    *,
    run_id: str = "",
    url: str = "",
    competitor: str = "",
    signal_type: str = "",
    content_hash: str = "",
    tokens: int = 0,
    model_name: str = "",
    event_count: int = 0,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a trace-safe metadata dict."""
    meta: Dict[str, Any] = {}
    if run_id:
        meta["run_id"] = run_id
    if url:
        meta["url_hash"] = hash_url(url)
        meta["url_host"] = urlparse(url).netloc
    if competitor:
        meta["competitor"] = competitor
    if signal_type:
        meta["signal_type"] = signal_type
    if content_hash:
        meta["content_hash"] = content_hash[:16]
    if tokens:
        meta["tokens"] = tokens
    if model_name:
        meta["model"] = model_name
    if event_count:
        meta["event_count"] = event_count
    if extra:
        for k, v in extra.items():
            if _SECRET_PATTERNS.search(k):
                meta[k] = "[REDACTED]"
            else:
                meta[k] = v
    return meta


class ObservabilityEmitter:
    """
    Emits structured trace records.
    Pluggable backend: currently 'log' only.
    Future: langfuse, langsmith adapters.
    """

    def __init__(self, provider: str = "log", redact: bool = True, max_text: int = 200):
        self.provider = provider
        self.redact = redact
        self.max_text = max_text
        self._spans: list = []

    def emit(self, span: SpanRecord) -> None:
        self._spans.append(span)
        if self.provider == "log":
            meta_str = " ".join(f"{k}={v}" for k, v in span.metadata.items())
            if span.status == "ok":
                logger.info(
                    f"[trace] {span.stage}  {span.duration_ms:.0f}ms  {meta_str}"
                )
            else:
                logger.warning(
                    f"[trace] {span.stage}  {span.duration_ms:.0f}ms  "
                    f"error={span.error_class} {span.error_message}  {meta_str}"
                )

    @contextmanager
    def span(self, stage: str, run_id: str = "", **meta_kwargs):
        """Context manager that times a pipeline stage and emits a span."""
        record = SpanRecord(
            stage=stage,
            run_id=run_id,
            started_at=time.time(),
        )
        record.metadata = safe_metadata(run_id=run_id, **meta_kwargs)
        try:
            yield record
            record.status = "ok"
        except Exception as e:
            record.status = "error"
            record.error_class = type(e).__name__
            record.error_message = scrub_error(str(e))
            raise
        finally:
            record.finished_at = time.time()
            record.duration_ms = (record.finished_at - record.started_at) * 1000
            self.emit(record)

    def get_spans(self) -> list:
        return list(self._spans)


_default_emitter: Optional[ObservabilityEmitter] = None


def get_emitter(provider: str = "log", redact: bool = True, max_text: int = 200) -> ObservabilityEmitter:
    global _default_emitter
    if _default_emitter is None:
        _default_emitter = ObservabilityEmitter(provider=provider, redact=redact, max_text=max_text)
    return _default_emitter


def reset_emitter() -> None:
    global _default_emitter
    _default_emitter = None
