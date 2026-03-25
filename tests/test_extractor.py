"""Tests for extractor.py — mocked LLM responses."""

import pytest
from unittest.mock import patch, MagicMock
from extractor import extract_events_from_text, _load_prompt_template


class TestLoadPromptTemplate:
    def test_developer_api_exists(self):
        template = _load_prompt_template("developer_api")
        assert "Developer API" in template

    def test_github_exists(self):
        template = _load_prompt_template("github")
        assert "GitHub" in template

    def test_fallback_to_generic(self):
        template = _load_prompt_template("nonexistent_signal")
        assert "weak signals" in template


class TestExtractEvents:
    @patch.dict("os.environ", {"GOOGLE_API_KEY": ""})
    def test_no_api_key(self):
        """Returns outcome with llm_no_api_key when no API key."""
        outcome = extract_events_from_text("some text", "https://example.com")
        assert outcome.events == []
        assert outcome.failure_kind == "llm_no_api_key"

    @patch("extractor.ChatGoogleGenerativeAI")
    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    def test_single_event_extraction(self, mock_model_class):
        """Mocked LLM returns a single event dict → wrapped in list."""
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        # Simulate the chain output (after parsing)
        mock_event = {
            "event_id": "e1",
            "competitor": "Siemens",
            "event_type": "API_UPDATE",
            "title": "New SDK Released",
            "description": "Siemens released a new Python SDK",
            "strategic_implication": "Threat to ABB",
            "confidence_score": 0.8,
            "source_url": "https://developer.siemens.com",
            "date_detected": "2026-03-19T00:00:00",
        }

        # Mock the chain pipeline (prompt | model | parser)
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = [mock_event]  # returns list

        with patch("extractor.PromptTemplate") as mock_pt:
            mock_prompt_instance = MagicMock()
            mock_pt.return_value = mock_prompt_instance
            mock_prompt_instance.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt_instance.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            outcome = extract_events_from_text(
                "Siemens released a new Python SDK",
                source_url="https://developer.siemens.com",
                competitor="Siemens",
                signal_type="developer_api",
            )

        assert isinstance(outcome.events, list)

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    @patch("extractor.ChatGoogleGenerativeAI")
    def test_no_crash_on_bad_llm_output(self, mock_model_class):
        """Gracefully handles unexpected LLM output."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "not a dict or list"

        with patch("extractor.PromptTemplate") as mock_pt:
            mock_prompt_instance = MagicMock()
            mock_pt.return_value = mock_prompt_instance
            mock_prompt_instance.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt_instance.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            outcome = extract_events_from_text(
                "some text", "https://example.com",
                competitor="Test", signal_type="generic",
            )
        assert isinstance(outcome.events, list)
        assert outcome.failure_kind == "llm_bad_output"
