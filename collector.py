"""
collector.py — Web scraper with retry logic and content hashing.
"""

import time
import logging
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional

from differ import compute_hash

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 2

# After stripping nav/script/etc., shorter text is usually a JS shell or block page.
MIN_VISIBLE_TEXT_CHARS = 40


@dataclass
class FetchResult:
    """Outcome of fetch_page_content (success or classified failure)."""
    text: str
    content_hash: str
    failure_category: Optional[str] = None
    http_status_code: Optional[int] = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.text and self.content_hash)


def fetch_page_content(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: int = DEFAULT_BACKOFF_FACTOR,
) -> FetchResult:
    """
    Fetch a URL and return visible text + content hash, or a classified failure.
    Retries with exponential backoff on failure.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    last_failure: Optional[FetchResult] = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[Attempt {attempt}/{max_retries}] Fetching: {url}")
            time.sleep(1)  # polite delay

            response = requests.get(url, headers=headers, timeout=timeout)
            status = response.status_code

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                detail = str(e)
                last_failure = FetchResult(
                    text="",
                    content_hash="",
                    failure_category="fetch_http_error",
                    http_status_code=status,
                    detail=detail,
                )
                wait = backoff_factor**attempt
                logger.warning(f"Attempt {attempt} HTTP error for {url}: {detail}")
                if attempt < max_retries:
                    logger.info(f"Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"All {max_retries} attempts failed for {url} (HTTP)")
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.extract()

            text = soup.get_text(separator=" ", strip=True)
            text = " ".join(text.split())

            if len(text) < MIN_VISIBLE_TEXT_CHARS:
                detail = (
                    f"Parsed visible text length {len(text)} chars "
                    f"(minimum {MIN_VISIBLE_TEXT_CHARS})"
                )
                logger.warning(f"{detail} for {url}")
                return FetchResult(
                    text="",
                    content_hash="",
                    failure_category="fetch_empty_parse",
                    http_status_code=status,
                    detail=detail,
                )

            content_hash = compute_hash(text)
            logger.info(f"Fetched {len(text)} chars from {url} (hash: {content_hash[:12]}...)")
            return FetchResult(text=text, content_hash=content_hash)

        except requests.exceptions.Timeout as e:
            last_failure = FetchResult(
                text="",
                content_hash="",
                failure_category="fetch_timeout",
                http_status_code=None,
                detail=str(e),
            )
            wait = backoff_factor**attempt
            logger.warning(f"Attempt {attempt} timeout for {url}: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"All {max_retries} attempts failed for {url} (timeout)")

        except requests.exceptions.ConnectionError as e:
            last_failure = FetchResult(
                text="",
                content_hash="",
                failure_category="fetch_connection",
                http_status_code=None,
                detail=str(e),
            )
            wait = backoff_factor**attempt
            logger.warning(f"Attempt {attempt} connection error for {url}: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"All {max_retries} attempts failed for {url} (connection)")

        except requests.exceptions.RequestException as e:
            last_failure = FetchResult(
                text="",
                content_hash="",
                failure_category="fetch_request_error",
                http_status_code=None,
                detail=str(e),
            )
            wait = backoff_factor**attempt
            logger.warning(f"Attempt {attempt} request error for {url}: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"All {max_retries} attempts failed for {url} (request)")

    if last_failure is not None:
        return last_failure
    return FetchResult(
        text="",
        content_hash="",
        failure_category="fetch_unknown",
        detail="No attempts completed",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    url = "https://developer.siemens.com/"
    result = fetch_page_content(url)
    print(f"OK: {result.ok}  Length: {len(result.text)}  Hash: {result.content_hash[:16] if result.content_hash else ''}...")
    print(f"Snippet: {result.text[:300]}")
