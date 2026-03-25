"""Tests for config_loader.py — config loading, validation, and URL guardrails."""

import pytest
import os
from pathlib import Path
from config_loader import get_config, get_all_target_urls, validate_url, AppConfig


class TestGetConfig:
    def test_load_valid_config(self, tmp_path):
        """Loads a valid YAML config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
project:
  name: RivalSense
  version: "0.4.0"
perspective:
  employer: ABB
  objective: Monitor competitors
competitors:
  - name: Siemens
    tier: 1
    focus_areas:
      - industrial automation
    urls:
      developer_api:
        - https://developer.siemens.com/
schedule:
  interval_hours: 12
llm:
  model: gemini-2.5-flash
  temperature: 0
  max_input_chars: 10000
collector:
  timeout_seconds: 10
  max_retries: 2
  backoff_factor: 3
alerts:
  enabled: true
  min_confidence: 0.8
  channels:
    - log
    - slack
""")
        cfg = get_config(config_path=config_file)
        assert cfg.project.name == "RivalSense"
        assert cfg.employer == "ABB"
        assert len(cfg.competitors) == 1
        assert cfg.competitors[0].name == "Siemens"
        assert cfg.schedule.interval_hours == 12
        assert cfg.alerts.enabled is True
        assert cfg.alerts.min_confidence == 0.8
        assert "slack" in cfg.alerts.channels

    def test_missing_file_uses_defaults(self, tmp_path):
        """Returns defaults when config file is missing."""
        cfg = get_config(config_path=tmp_path / "nonexistent.yaml")
        assert isinstance(cfg, AppConfig)
        assert cfg.employer == "ABB"
        assert len(cfg.competitors) == 0
        assert cfg.alerts.enabled is False

    def test_empty_file_uses_defaults(self, tmp_path):
        """Empty YAML returns defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        cfg = get_config(config_path=config_file)
        assert isinstance(cfg, AppConfig)

    def test_v3_defaults(self, tmp_path):
        """V3 sections have sensible defaults even when not in YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("project:\n  name: Test\n")
        cfg = get_config(config_path=config_file)
        assert cfg.observability.enabled is True
        assert cfg.observability.provider == "log"
        assert cfg.budget.max_tokens_per_run == 500_000
        assert cfg.auth.provider == "none"
        assert cfg.retention.events_days == 365


class TestGetAllTargetUrls:
    def test_flatten_urls(self):
        cfg = AppConfig(
            competitors=[
                {"name": "Siemens", "urls": {"developer_api": ["https://a.com", "https://b.com"]}},
                {"name": "ABB", "urls": {"github": ["https://github.com/abb"]}},
            ]
        )
        targets = get_all_target_urls(cfg)
        assert len(targets) == 3
        assert targets[0]["competitor"] == "Siemens"
        assert targets[0]["signal_type"] == "developer_api"
        assert targets[2]["competitor"] == "ABB"

    def test_no_competitors(self):
        cfg = AppConfig(competitors=[])
        assert get_all_target_urls(cfg) == []

    def test_file_scheme_blocked(self):
        """file: URLs should be rejected by get_all_target_urls."""
        cfg = AppConfig(
            competitors=[
                {"name": "Test", "urls": {"test": ["file:///etc/passwd"]}},
            ]
        )
        targets = get_all_target_urls(cfg)
        assert len(targets) == 0


class TestValidateUrl:
    def test_valid_https(self):
        warnings = validate_url("https://developer.siemens.com/")
        assert warnings == []

    def test_file_scheme(self):
        warnings = validate_url("file:///etc/passwd")
        assert any("file:" in w for w in warnings)

    def test_private_ip(self):
        warnings = validate_url("http://192.168.1.1/admin")
        assert any("Private" in w or "private" in w.lower() for w in warnings)

    def test_localhost(self):
        warnings = validate_url("http://localhost:8080")
        assert any("Localhost" in w for w in warnings)

    def test_cloud_metadata(self):
        warnings = validate_url("http://169.254.169.254/latest/meta-data/")
        assert any("metadata" in w.lower() for w in warnings)

    def test_strict_non_https(self):
        warnings = validate_url("http://example.com", strict=True)
        assert any("Non-HTTPS" in w for w in warnings)
