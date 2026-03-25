"""
extractor.py — V2 multi-event LLM extraction with signal-specific prompts
and confidence calibration.
"""

import os
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from schema import CompetitorEvent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)


@dataclass
class ExtractionOutcome:
    """Result of LLM extraction: events and optional failure classification."""
    events: List[CompetitorEvent]
    failure_kind: Optional[str] = None
    detail: str = ""


# ───────────────────────────────────────────────────────────────
# Shared extraction policy (prepended to every signal template)
# ───────────────────────────────────────────────────────────────

SHARED_EXTRACTION_POLICY = """
GLOBAL POLICY (apply to every extraction):
- You support ABB competitive intelligence. Known competitors in scope: Siemens, Schneider Electric, Rockwell Automation.
- Ground every event in the provided content only. Do not invent facts, versions, dates, URLs, or quotes not supported by the text.
- If there is no defensible weak signal, return an empty JSON array: []
- description: factual what changed or what was observed; cite short phrases from the content when helpful.
- strategic_implication: why it may matter to ABB; do not repeat the entire description.
- Use conservative confidence_score values; a second pass may recalibrate scores.
- If diff_context indicates changes, any event that claims something NEW or CHANGED must be consistent with that evidence.
""".strip()

# ───────────────────────────────────────────────────────────────
# Prompt loader
# ───────────────────────────────────────────────────────────────

PROMPTS_DIR = Path(__file__).parent / "prompts"

def _load_prompt_template(signal_type: str) -> str:
    """Load the signal-specific prompt file, falling back to generic."""
    specific = PROMPTS_DIR / f"{signal_type}.txt"
    generic  = PROMPTS_DIR / "generic.txt"

    if specific.exists():
        logger.info(f"Using prompt template: {specific.name}")
        return specific.read_text(encoding="utf-8")
    elif generic.exists():
        logger.info(f"No prompt for '{signal_type}' — using generic.txt")
        return generic.read_text(encoding="utf-8")
    else:
        raise FileNotFoundError(f"No prompt templates found in {PROMPTS_DIR}")

# ───────────────────────────────────────────────────────────────
# Confidence calibration
# ───────────────────────────────────────────────────────────────

CALIBRATION_PROMPT = """
You are a senior intelligence analyst. These events were extracted from a single
source run for competitive intelligence (ABB perspective).

Source signal workflow (config category): {signal_type}

Re-evaluate each confidence_score using this rubric:

- Source reliability: developer portal / official press > corporate marketing page > blog > forum / social.
- Specificity: prefer concrete artifacts (version numbers, API paths, repo names, patent numbers, addresses,
  product names, dates) over vague language ("innovation", "digital transformation") unless the source is highly authoritative.
- Marketing-only language: if the title/description is generic marketing with no new factual anchor, reduce score sharply.
- Change claims: if an event implies something NEW or CHANGED, the description must contain supporting evidence;
  if the evidence is thin or purely rhetorical, reduce confidence.
- Corroboration: could this be verified from another public source? Lack of corroboration caps scores for noisy sources.
- Actionability: does this plausibly require a strategic response from ABB?

Scoring guide:
  0.1–0.3  Speculative / weak evidence
  0.4–0.6  Moderate evidence, worth monitoring
  0.7–0.9  Strong, concrete evidence
  1.0      Confirmed announcement (rare; only for explicit official confirmations in the text)

Return the SAME JSON array with updated confidence_score values only.
Do NOT add or remove events.

Events to calibrate:
{events_json}

{format_instructions}
"""

# ───────────────────────────────────────────────────────────────
# Main extraction
# ───────────────────────────────────────────────────────────────

def extract_events_from_text(
    text: str,
    source_url: str,
    competitor: str = "Unknown",
    signal_type: str = "generic",
    diff_summary: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0,
    max_input_chars: int = 15000,
) -> ExtractionOutcome:
    """
    Extract strategic events from raw text using a signal-specific prompt.
    Returns ExtractionOutcome with events (possibly empty) and failure_kind when nothing usable was extracted.
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        logger.warning("GOOGLE_API_KEY not set — extraction will fail")
        return ExtractionOutcome(
            [],
            failure_kind="llm_no_api_key",
            detail="GOOGLE_API_KEY not set",
        )

    try:
        # Build diff context block
        diff_context = ""
        if diff_summary and diff_summary != "No textual differences detected.":
            diff_context = (
                "The following CHANGES were detected compared to the previous scrape:\n"
                f"```\n{diff_summary}\n```\n"
                "Focus your analysis on these changes.\n"
            )

        # Load signal-specific prompt and prepend shared policy
        template_text = SHARED_EXTRACTION_POLICY + "\n\n" + _load_prompt_template(signal_type)

        # JSON output parser for a list of events
        parser = JsonOutputParser()

        # Build format instructions that describe the expected output
        format_instructions = (
            "Return a JSON array of objects. Each object must have these keys:\n"
            "event_id (string, unique UUID), competitor (string), event_type (string),\n"
            "title (string), description (string), strategic_implication (string),\n"
            "confidence_score (float 0.0-1.0), source_url (string), date_detected (string, ISO format).\n"
            "If no meaningful events are found, return an empty array: []"
        )

        prompt = PromptTemplate(
            template=template_text,
            input_variables=["content", "source_url", "competitor", "current_date", "diff_context"],
            partial_variables={"format_instructions": format_instructions},
        )

        model = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
        chain = prompt | model | parser

        logger.info(f"Extracting events from {source_url} ({len(text)} chars, signal={signal_type})")
        raw_result = chain.invoke({
            "content": text[:max_input_chars],
            "source_url": source_url,
            "competitor": competitor,
            "current_date": datetime.now().isoformat(),
            "diff_context": diff_context,
        })

        # Normalise: ensure we always have a list
        if isinstance(raw_result, dict):
            raw_result = [raw_result]
        if not isinstance(raw_result, list):
            logger.warning(f"Unexpected LLM output type: {type(raw_result)}")
            return ExtractionOutcome(
                [],
                failure_kind="llm_bad_output",
                detail=f"Expected list or dict, got {type(raw_result).__name__}",
            )

        # Parse into Pydantic models
        events: List[CompetitorEvent] = []
        for item in raw_result:
            if not isinstance(item, dict):
                continue
            # Ensure required fields
            item.setdefault("event_id", str(uuid.uuid4()))
            item.setdefault("source_url", source_url)
            item.setdefault("date_detected", datetime.now().isoformat())
            item.setdefault("competitor", competitor)
            try:
                event = CompetitorEvent(**item)
                events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}")

        logger.info(f"Extracted {len(events)} event(s) from {source_url}")

        if not events:
            if raw_result == []:
                return ExtractionOutcome([], failure_kind="llm_no_events", detail="")
            return ExtractionOutcome(
                [],
                failure_kind="llm_event_parse_error",
                detail="LLM returned data that did not validate as CompetitorEvent",
            )

        # Calibrate confidence if we got events
        events = _calibrate_confidence(
            events, model_name, temperature, signal_type=signal_type
        )

        return ExtractionOutcome(events)

    except Exception as e:
        logger.error(f"Extraction failed for {source_url}: {e}")
        return ExtractionOutcome(
            [],
            failure_kind="llm_extraction_error",
            detail=str(e),
        )

# ───────────────────────────────────────────────────────────────
# Confidence calibration (second pass)
# ───────────────────────────────────────────────────────────────

def _calibrate_confidence(
    events: List[CompetitorEvent],
    model_name: str,
    temperature: float,
    signal_type: str = "generic",
) -> List[CompetitorEvent]:
    """Re-evaluate confidence scores with a calibration prompt."""
    try:
        import json
        events_json = json.dumps([e.model_dump() for e in events], indent=2)

        parser = JsonOutputParser()
        format_instructions = (
            "Return the exact same JSON array with only confidence_score values adjusted.\n"
            "Do NOT change any other fields. Do NOT add or remove events."
        )

        prompt = PromptTemplate(
            template=CALIBRATION_PROMPT,
            input_variables=["events_json", "signal_type"],
            partial_variables={"format_instructions": format_instructions},
        )

        model = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
        chain = prompt | model | parser

        logger.info("Running confidence calibration pass...")
        calibrated = chain.invoke({
            "events_json": events_json,
            "signal_type": signal_type,
        })

        if isinstance(calibrated, dict):
            calibrated = [calibrated]
        if not isinstance(calibrated, list):
            logger.warning("Calibration returned unexpected format — keeping original scores")
            return events

        # Update only the confidence scores
        for i, item in enumerate(calibrated):
            if i < len(events) and isinstance(item, dict) and "confidence_score" in item:
                old = events[i].confidence_score
                new = float(item["confidence_score"])
                if old != new:
                    logger.info(f"Calibrated '{events[i].title}': {old:.2f} → {new:.2f}")
                events[i].confidence_score = new

        return events

    except Exception as e:
        logger.warning(f"Calibration failed (keeping original scores): {e}")
        return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_text = (
        "Siemens today announced version 2.0 of the Xcelerator Developer API, "
        "featuring new endpoints for Edge Device Management and cloud-to-edge "
        "deployment synchronization. A new Python SDK was also released."
    )
    print("Testing extraction (requires GOOGLE_API_KEY)...")
    outcome = extract_events_from_text(
        test_text,
        source_url="https://developer.siemens.com/news",
        competitor="Siemens",
        signal_type="developer_api",
    )
    for r in outcome.events:
        print(f"  → {r.title} (confidence: {r.confidence_score:.2f})")
