"""Tests for observability.py — redacted tracing."""

import pytest
from observability import (
    redact_secret_values, strip_url_query, hash_url,
    truncate_text, scrub_error, safe_metadata,
    ObservabilityEmitter,
)


class TestRedaction:
    def test_redact_api_key(self):
        text = "GOOGLE_API_KEY=sk-abc123xyz"
        result = redact_secret_values(text)
        assert "sk-abc123xyz" not in result
        assert "[REDACTED]" in result

    def test_redact_webhook(self):
        text = "webhook_url=https://hooks.slack.com/services/T123/B456"
        result = redact_secret_values(text)
        assert "[REDACTED]" in result

    def test_passthrough_safe_text(self):
        text = "This is a normal log message"
        assert redact_secret_values(text) == text


class TestUrlSafety:
    def test_strip_query(self):
        url = "https://example.com/page?token=secret&id=123"
        result = strip_url_query(url)
        assert "token" not in result
        assert "secret" not in result
        assert "example.com/page" in result

    def test_hash_url(self):
        h = hash_url("https://developer.siemens.com/")
        assert len(h) == 16
        assert h == hash_url("https://developer.siemens.com/")


class TestTruncation:
    def test_short_text_unchanged(self):
        assert truncate_text("hello", max_chars=100) == "hello"

    def test_long_text_truncated(self):
        long_text = "x" * 500
        result = truncate_text(long_text, max_chars=100)
        assert len(result) < 200
        assert "truncated" in result
        assert "sha256=" in result


class TestScrubError:
    def test_scrub_removes_secrets(self):
        msg = "Failed: api_key=sk-123abc detail here"
        result = scrub_error(msg)
        assert "sk-123abc" not in result

    def test_truncates_long_errors(self):
        msg = "x" * 1000
        result = scrub_error(msg)
        assert len(result) <= 500


class TestSafeMetadata:
    def test_basic_metadata(self):
        meta = safe_metadata(
            run_id="r1", url="https://example.com",
            competitor="Siemens", signal_type="developer_api",
        )
        assert meta["run_id"] == "r1"
        assert "url_hash" in meta
        assert meta["competitor"] == "Siemens"
        assert "example.com" not in meta.get("url_hash", "")

    def test_redacts_secret_keys(self):
        meta = safe_metadata(extra={"API_KEY": "secret_value"})
        assert meta["API_KEY"] == "[REDACTED]"


class TestEmitter:
    def test_span_records(self):
        emitter = ObservabilityEmitter(provider="log")
        with emitter.span("test_stage", run_id="r1"):
            pass
        spans = emitter.get_spans()
        assert len(spans) == 1
        assert spans[0].stage == "test_stage"
        assert spans[0].status == "ok"
        assert spans[0].duration_ms >= 0

    def test_span_error(self):
        emitter = ObservabilityEmitter(provider="log")
        with pytest.raises(ValueError):
            with emitter.span("failing_stage", run_id="r1"):
                raise ValueError("test error")
        spans = emitter.get_spans()
        assert spans[0].status == "error"
        assert "ValueError" in spans[0].error_class
