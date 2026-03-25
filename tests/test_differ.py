"""Tests for differ.py — hashing and diff summaries."""

import pytest
from differ import compute_hash, get_diff_summary


class TestComputeHash:
    def test_deterministic(self):
        """Same input produces same hash."""
        assert compute_hash("hello") == compute_hash("hello")

    def test_different_inputs(self):
        """Different inputs produce different hashes."""
        assert compute_hash("hello") != compute_hash("world")

    def test_sha256_length(self):
        """Output is a 64-char hex string (SHA-256)."""
        assert len(compute_hash("test")) == 64

    def test_empty_string(self):
        """Empty string produces a valid hash."""
        h = compute_hash("")
        assert len(h) == 64


class TestGetDiffSummary:
    def test_no_change(self):
        text = "Line 1\nLine 2"
        result = get_diff_summary(text, text)
        assert "No textual differences" in result

    def test_addition(self):
        old = "Line 1\nLine 2"
        new = "Line 1\nLine 2\nLine 3"
        result = get_diff_summary(old, new)
        assert "+Line 3" in result

    def test_removal(self):
        old = "Line 1\nLine 2\nLine 3"
        new = "Line 1\nLine 3"
        result = get_diff_summary(old, new)
        assert "-Line 2" in result

    def test_truncation(self):
        """Long diffs are truncated."""
        old = "\n".join(f"old line {i}" for i in range(100))
        new = "\n".join(f"new line {i}" for i in range(100))
        result = get_diff_summary(old, new, max_lines=10)
        assert "more lines" in result
