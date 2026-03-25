"""
differ.py — Change detection via SHA-256 hashing and text diffing.
"""

import hashlib
import difflib
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def compute_hash(text: str) -> str:
    """Compute a SHA-256 hash of the given text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def has_changed(url: str, current_hash: str) -> bool:
    """
    Check whether the content at `url` has changed compared to the last
    stored snapshot.  Returns True if changed or if no previous snapshot exists.
    """
    from db import get_last_snapshot  # late import to avoid circular deps
    snapshot = get_last_snapshot(url)
    if snapshot is None:
        logger.info(f"No previous snapshot for {url} — treating as new")
        return True
    changed = snapshot["content_hash"] != current_hash
    if changed:
        logger.info(f"Content changed for {url}")
    else:
        logger.info(f"No change detected for {url}")
    return changed


def get_previous_text(url: str) -> Optional[str]:
    """Retrieve the raw text of the last stored snapshot for a URL."""
    from db import get_last_snapshot
    snapshot = get_last_snapshot(url)
    if snapshot and snapshot.get("raw_text"):
        return snapshot["raw_text"]
    return None


def get_diff_summary(old_text: str, new_text: str, max_lines: int = 30) -> str:
    """
    Generate a human-readable diff summary between two text blobs.
    Returns a string summarising the key additions and removals.
    """
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    diff = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile="previous", tofile="current",
        lineterm=""
    ))

    if not diff:
        return "No textual differences detected."

    # Truncate if too long
    if len(diff) > max_lines:
        diff = diff[:max_lines] + [f"... ({len(diff) - max_lines} more lines)"]

    return "\n".join(diff)


if __name__ == "__main__":
    # Quick self-test
    old = "Siemens Developer Portal\nAPI v1.0\nEndpoints: 5"
    new = "Siemens Developer Portal\nAPI v2.0\nEndpoints: 12\nNew: Edge Management SDK"
    h1 = compute_hash(old)
    h2 = compute_hash(new)
    print(f"Hash old: {h1[:16]}...  Hash new: {h2[:16]}...")
    print(f"Changed: {h1 != h2}")
    print("--- Diff ---")
    print(get_diff_summary(old, new))
