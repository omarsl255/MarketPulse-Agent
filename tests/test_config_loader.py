"""Tests for config_loader.py — config loading and validation."""

import pytest
import tempfile
import os
from pathlib import Path
from config_loader import get_config, get_all_target_urls, AppConfig


class TestGetConfig:
    def test_load_valid_config(self, tmp_path):
        """Loads a valid YAML config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
project:
  name: RivalSense
  version: "0.3.0"
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
""")
        cfg = get_config(config_path=config_file)
        assert cfg.project.name == "RivalSense"
        assert cfg.employer == "ABB"
        assert len(cfg.competitors) == 1
        assert cfg.competitors[0].name == "Siemens"
        assert cfg.competitors[0].tier == 1
        assert "industrial automation" in cfg.competitors[0].focus_areas
        assert cfg.schedule.interval_hours == 12
        assert cfg.llm.max_input_chars == 10000
        assert cfg.collector.max_retries == 2

    def test_missing_file_uses_defaults(self, tmp_path):
        """Returns defaults when config file is missing."""
        cfg = get_config(config_path=tmp_path / "nonexistent.yaml")
        assert isinstance(cfg, AppConfig)
        assert cfg.employer == "ABB"
        assert len(cfg.competitors) == 0

    def test_empty_file_uses_defaults(self, tmp_path):
        """Empty YAML returns defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        cfg = get_config(config_path=config_file)
        assert isinstance(cfg, AppConfig)


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
