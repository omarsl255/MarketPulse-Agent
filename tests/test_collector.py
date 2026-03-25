"""Tests for collector.py — mocked HTTP requests."""

import pytest
from unittest.mock import patch, MagicMock
from collector import fetch_page_content, FetchResult


@pytest.fixture
def mock_html():
    # Must exceed collector.MIN_VISIBLE_TEXT_CHARS after stripping nav/scripts.
    return (
        "<html><body><h1>Siemens Developer Portal</h1><p>API v2.0</p>"
        "<p>Additional developer documentation and release notes for the platform.</p>"
        "</body></html>"
    )


class TestFetchPageContent:
    @patch("collector.requests.get")
    def test_success(self, mock_get, mock_html):
        """Successful fetch returns text and hash."""
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_page_content("https://example.com", max_retries=1)
        assert isinstance(result, FetchResult)
        assert "Siemens Developer Portal" in result.text
        assert "API v2.0" in result.text
        assert len(result.content_hash) == 64  # SHA-256
        assert result.ok
        assert result.failure_category is None
        mock_get.assert_called_once()

    @patch("collector.requests.get")
    def test_strips_scripts(self, mock_get):
        """Scripts, styles, nav, footer, header are stripped."""
        html = (
            "<html><script>evil()</script><nav>nav</nav><body>"
            "<p>Content</p><p>More visible body text so the scrape meets the minimum length threshold.</p>"
            "</body></html>"
        )
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_page_content("https://example.com", max_retries=1)
        assert "evil" not in result.text
        assert "nav" not in result.text
        assert "Content" in result.text
        assert result.ok

    @patch("collector.requests.get")
    def test_timeout_retries(self, mock_get):
        """Retries on request exception, returns classified failure on exhaustion."""
        from requests.exceptions import Timeout
        mock_get.side_effect = Timeout("timed out")

        result = fetch_page_content(
            "https://example.com", max_retries=2, backoff_factor=0
        )
        assert result.text == ""
        assert result.content_hash == ""
        assert result.failure_category == "fetch_timeout"
        assert mock_get.call_count == 2

    @patch("collector.requests.get")
    def test_404(self, mock_get):
        """HTTP error triggers retry; final outcome is fetch_http_error."""
        from requests.exceptions import HTTPError
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        result = fetch_page_content(
            "https://example.com", max_retries=1, backoff_factor=0
        )
        assert not result.ok
        assert result.failure_category == "fetch_http_error"
        assert result.http_status_code == 404

    @patch("collector.requests.get")
    def test_empty_parse_after_200(self, mock_get):
        """Very little visible text after parse → fetch_empty_parse (no retries)."""
        mock_response = MagicMock()
        mock_response.text = "<html><body></body></html>"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_page_content("https://example.com", max_retries=3, backoff_factor=0)
        assert not result.ok
        assert result.failure_category == "fetch_empty_parse"
        assert result.http_status_code == 200
        assert mock_get.call_count == 1
