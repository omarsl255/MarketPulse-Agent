"""
evaluator.py — Golden-set evaluation harness for V3.
Compares extraction output against labeled examples to measure
precision/recall when prompts or models change.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from schema import CompetitorEvent

logger = logging.getLogger("evaluator")

GOLDEN_SET_DIR = Path(__file__).parent / "golden_sets"


@dataclass
class EvalCase:
    """A single evaluation case: input text + expected events."""
    case_id: str
    signal_type: str
    competitor: str
    source_url: str
    input_text: str
    expected_events: List[Dict[str, Any]]
    tags: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Result of evaluating one case."""
    case_id: str
    expected_count: int
    extracted_count: int
    matched: int
    precision: float
    recall: float
    f1: float
    details: List[str] = field(default_factory=list)


@dataclass
class EvalSummary:
    """Aggregate evaluation results."""
    total_cases: int
    avg_precision: float
    avg_recall: float
    avg_f1: float
    per_case: List[EvalResult] = field(default_factory=list)
    per_signal_type: Dict[str, Dict[str, float]] = field(default_factory=dict)


def load_golden_set(signal_type: str) -> List[EvalCase]:
    """Load golden-set cases from a JSON file."""
    path = GOLDEN_SET_DIR / f"{signal_type}.json"
    if not path.exists():
        logger.info(f"No golden set found at {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    cases = []
    for item in raw:
        cases.append(EvalCase(
            case_id=item.get("case_id", ""),
            signal_type=item.get("signal_type", signal_type),
            competitor=item.get("competitor", ""),
            source_url=item.get("source_url", ""),
            input_text=item.get("input_text", ""),
            expected_events=item.get("expected_events", []),
            tags=item.get("tags", []),
        ))
    logger.info(f"Loaded {len(cases)} golden-set cases for '{signal_type}'")
    return cases


def _event_matches(expected: Dict[str, Any], actual: CompetitorEvent) -> bool:
    """
    Check if an extracted event matches an expected event.
    Matching is fuzzy: event_type must match, and title must share
    significant overlap (>50% word overlap).
    """
    if expected.get("event_type", "").lower() != actual.event_type.lower():
        return False

    expected_words = set(expected.get("title", "").lower().split())
    actual_words = set(actual.title.lower().split())
    if not expected_words or not actual_words:
        return False

    overlap = len(expected_words & actual_words) / max(len(expected_words), 1)
    return overlap > 0.5


def evaluate_case(case: EvalCase, extracted_events: List[CompetitorEvent]) -> EvalResult:
    """Evaluate extracted events against a golden-set case."""
    expected = case.expected_events
    n_expected = len(expected)
    n_extracted = len(extracted_events)
    details: List[str] = []

    matched_expected = set()
    matched_extracted = set()

    for i, exp in enumerate(expected):
        for j, act in enumerate(extracted_events):
            if j in matched_extracted:
                continue
            if _event_matches(exp, act):
                matched_expected.add(i)
                matched_extracted.add(j)
                details.append(f"MATCH: expected[{i}] ~ extracted[{j}]")
                break

    n_matched = len(matched_expected)
    precision = n_matched / max(n_extracted, 1)
    recall = n_matched / max(n_expected, 1)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    for i in range(n_expected):
        if i not in matched_expected:
            details.append(f"MISS: expected[{i}] '{expected[i].get('title', '')}' not found")
    for j in range(n_extracted):
        if j not in matched_extracted:
            details.append(f"EXTRA: extracted[{j}] '{extracted_events[j].title}' not expected")

    return EvalResult(
        case_id=case.case_id,
        expected_count=n_expected,
        extracted_count=n_extracted,
        matched=n_matched,
        precision=round(precision, 3),
        recall=round(recall, 3),
        f1=round(f1, 3),
        details=details,
    )


def run_evaluation(
    signal_type: str,
    extractor_fn,
    *,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0,
    max_input_chars: int = 15000,
) -> Optional[EvalSummary]:
    """
    Run the full evaluation harness for a signal type.
    extractor_fn should be extract_events_from_text or equivalent.
    """
    cases = load_golden_set(signal_type)
    if not cases:
        logger.info(f"No golden set for {signal_type} — skipping evaluation")
        return None

    results: List[EvalResult] = []

    for case in cases:
        try:
            outcome = extractor_fn(
                text=case.input_text,
                source_url=case.source_url,
                competitor=case.competitor,
                signal_type=case.signal_type,
                model_name=model_name,
                temperature=temperature,
                max_input_chars=max_input_chars,
            )
            result = evaluate_case(case, outcome.events)
        except Exception as e:
            logger.error(f"Evaluation failed for case {case.case_id}: {e}")
            result = EvalResult(
                case_id=case.case_id,
                expected_count=len(case.expected_events),
                extracted_count=0, matched=0,
                precision=0.0, recall=0.0, f1=0.0,
                details=[f"ERROR: {str(e)[:200]}"],
            )
        results.append(result)

    if not results:
        return None

    avg_p = sum(r.precision for r in results) / len(results)
    avg_r = sum(r.recall for r in results) / len(results)
    avg_f1 = sum(r.f1 for r in results) / len(results)

    by_signal: Dict[str, Dict[str, float]] = {}
    for case, result in zip(cases, results):
        st = case.signal_type
        if st not in by_signal:
            by_signal[st] = {"precision": 0, "recall": 0, "f1": 0, "count": 0}
        by_signal[st]["precision"] += result.precision
        by_signal[st]["recall"] += result.recall
        by_signal[st]["f1"] += result.f1
        by_signal[st]["count"] += 1

    for st in by_signal:
        n = by_signal[st]["count"]
        by_signal[st] = {
            "precision": round(by_signal[st]["precision"] / n, 3),
            "recall": round(by_signal[st]["recall"] / n, 3),
            "f1": round(by_signal[st]["f1"] / n, 3),
        }

    summary = EvalSummary(
        total_cases=len(results),
        avg_precision=round(avg_p, 3),
        avg_recall=round(avg_r, 3),
        avg_f1=round(avg_f1, 3),
        per_case=results,
        per_signal_type=by_signal,
    )

    logger.info(
        f"Evaluation complete for '{signal_type}': "
        f"{summary.total_cases} cases, "
        f"P={summary.avg_precision:.3f} R={summary.avg_recall:.3f} F1={summary.avg_f1:.3f}"
    )
    return summary
