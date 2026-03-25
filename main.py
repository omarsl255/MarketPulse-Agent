"""
main.py — V2 pipeline orchestrator.
Collect → Diff → Extract → Store for all configured competitors.
"""

import os
import uuid
import logging
from datetime import datetime

from config_loader import load_secrets, get_config, get_all_target_urls
from collector import fetch_page_content, FetchResult
from differ import has_changed, get_previous_text, get_diff_summary
from extractor import extract_events_from_text
from db import init_db, save_event, save_snapshot, save_failed_extraction
from schema import CompetitorEvent, FailedExtraction

# ───────────────────────────────────────────────────────────────
# Logging setup
# ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pipeline")


def _fetch_error_message(fr: FetchResult) -> str:
    cat = fr.failure_category or "fetch_failed"
    if fr.http_status_code is not None:
        base = f"{cat} (HTTP {fr.http_status_code})"
    else:
        base = cat
    if fr.detail:
        return f"{base}: {fr.detail[:300]}"
    return base


def _llm_failure_message(failure_kind: str, detail: str) -> str:
    if failure_kind == "llm_no_events":
        return "LLM returned no events"
    if failure_kind == "llm_no_api_key":
        return "GOOGLE_API_KEY not set"
    if failure_kind == "llm_bad_output":
        return f"Unexpected LLM output: {detail[:200]}" if detail else "Unexpected LLM output"
    if failure_kind == "llm_event_parse_error":
        return "LLM output did not produce valid events"
    if failure_kind == "llm_extraction_error":
        return f"Extraction error: {detail[:200]}" if detail else "Extraction error"
    return detail[:300] if detail else failure_kind


def run_pipeline() -> dict:
    """
    Execute one full intelligence-gathering run.
    Returns a summary dict with run statistics.
    """
    run_id = str(uuid.uuid4())[:8]
    logger.info(f"{'='*60}")
    logger.info(f"Starting pipeline run [{run_id}]")
    logger.info(f"{'='*60}")

    # Load config & secrets
    load_secrets()
    config = get_config()
    init_db()

    targets = get_all_target_urls(config)
    logger.info(f"Targets: {len(targets)} URLs across {len(config.competitors)} competitors")

    stats = {
        "run_id": run_id,
        "total_urls": len(targets),
        "urls_changed": 0,
        "urls_unchanged": 0,
        "urls_failed": 0,
        "events_extracted": 0,
        "extractions_failed": 0,
    }

    for target in targets:
        url = target["url"]
        competitor = target["competitor"]
        signal_type = target["signal_type"]
        logger.info(f"--- [{competitor}] [{signal_type}] {url}")

        # 1. COLLECT
        fetch_result = fetch_page_content(
            url,
            timeout=config.collector.timeout_seconds,
            max_retries=config.collector.max_retries,
            backoff_factor=config.collector.backoff_factor,
        )

        if not fetch_result.text:
            logger.warning(f"Failed to fetch {url} — skipping")
            stats["urls_failed"] += 1
            save_failed_extraction(FailedExtraction(
                id=str(uuid.uuid4()),
                url=url,
                error_message=_fetch_error_message(fetch_result),
                raw_text_snippet="",
                timestamp=datetime.now().isoformat(),
                run_id=run_id,
                failure_category=fetch_result.failure_category or "fetch_unknown",
                http_status_code=fetch_result.http_status_code,
                detail=fetch_result.detail[:2000] if fetch_result.detail else "",
            ))
            continue

        text, content_hash = fetch_result.text, fetch_result.content_hash

        # 2. DIFF — check if content changed
        changed = has_changed(url, content_hash)

        if not changed:
            logger.info(f"No changes detected for {url} — skipping extraction")
            stats["urls_unchanged"] += 1
            continue

        stats["urls_changed"] += 1

        # Get diff summary for LLM context
        old_text = get_previous_text(url)
        diff_summary = None
        if old_text:
            diff_summary = get_diff_summary(old_text, text)
            logger.info(f"Generated diff summary ({len(diff_summary)} chars)")

        # 3. EXTRACT — use LLM to find events
        if os.environ.get("GOOGLE_API_KEY"):
            outcome = extract_events_from_text(
                text=text,
                source_url=url,
                competitor=competitor,
                signal_type=signal_type,
                diff_summary=diff_summary,
                model_name=config.llm.model,
                temperature=config.llm.temperature,
                max_input_chars=config.llm.max_input_chars,
            )
            events = outcome.events
        else:
            logger.warning("No GOOGLE_API_KEY — generating mock event")
            events = [CompetitorEvent(
                event_id=str(uuid.uuid4()),
                competitor=competitor,
                event_type="MOCK_SIGNAL",
                title=f"Mock: {competitor} signal from {signal_type}",
                description=f"Scraped {len(text)} chars from {url}. Set GOOGLE_API_KEY for real extraction.",
                strategic_implication=f"{competitor} activity detected on {signal_type} — requires GOOGLE_API_KEY for analysis.",
                confidence_score=0.2,
                source_url=url,
                date_detected=datetime.now().isoformat(),
                run_id=run_id,
                signal_type=signal_type,
                content_hash=content_hash,
                is_new=True,
            )]

        if not events:
            if os.environ.get("GOOGLE_API_KEY"):
                fk = outcome.failure_kind or "llm_no_events"
                detail = outcome.detail
                em = _llm_failure_message(fk, detail)
            else:
                fk = "unexpected_empty_events"
                detail = ""
                em = "No events to store (unexpected without LLM)"
            logger.info(f"No events extracted from {url} ({fk})")
            save_failed_extraction(FailedExtraction(
                id=str(uuid.uuid4()),
                url=url,
                error_message=em,
                raw_text_snippet=text[:500],
                timestamp=datetime.now().isoformat(),
                run_id=run_id,
                failure_category=fk,
                http_status_code=None,
                detail=(detail[:2000] if detail else ""),
            ))
            stats["extractions_failed"] += 1

        # 4. STORE — save events and update snapshot
        for event in events:
            event.run_id = run_id
            event.signal_type = signal_type
            event.content_hash = content_hash
            event.is_new = True
            save_event(event)
            logger.info(f"  ✓ Saved: {event.title} (confidence: {event.confidence_score:.2f})")

        stats["events_extracted"] += len(events)

        # Save snapshot for future diffing
        save_snapshot(url, content_hash, text, datetime.now().isoformat())

    # Print summary
    logger.info(f"{'='*60}")
    logger.info(f"Run [{run_id}] complete")
    logger.info(f"  URLs processed: {stats['total_urls']}")
    logger.info(f"  Changed:        {stats['urls_changed']}")
    logger.info(f"  Unchanged:      {stats['urls_unchanged']}")
    logger.info(f"  Failed:         {stats['urls_failed']}")
    logger.info(f"  Events found:   {stats['events_extracted']}")
    logger.info(f"{'='*60}")

    return stats


if __name__ == "__main__":
    run_pipeline()
