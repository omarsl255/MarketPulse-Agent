"""
agent.py — Governed agent layer for V3.
Provides constrained analyst workflows with:
- Explicit tool allowlists
- URL policies
- Audit logging
- Max-step limits
- Manual approval gates for high-impact actions
"""

import uuid
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any

from schema import CompetitorEvent

logger = logging.getLogger("agent")


# ───────────────────────────────────────────────────────────────
# Policies and governance
# ───────────────────────────────────────────────────────────────

ALLOWED_TOOLS = {
    "summarize_events",
    "build_timeline",
    "generate_competitor_brief",
    "correlate_signals",
    "search_events",
}

BLOCKED_TOOLS = {
    "browse_arbitrary_url",
    "execute_code",
    "modify_database",
    "send_external_request",
}

MAX_STEPS_PER_TASK = 10
MAX_EVENTS_PER_EXPORT = 100


@dataclass
class AuditEntry:
    """Immutable record of an agent action for the audit log."""
    entry_id: str
    task_id: str
    tool_name: str
    timestamp: str
    input_summary: str
    output_summary: str
    status: str  # "allowed", "blocked", "requires_approval"
    reviewer: str = ""
    approved: bool = False


@dataclass
class AgentTask:
    """A bounded analyst workflow task."""
    task_id: str
    task_type: str
    description: str
    status: str = "pending"  # pending, running, completed, failed, awaiting_approval
    created_at: str = ""
    completed_at: str = ""
    steps_taken: int = 0
    max_steps: int = MAX_STEPS_PER_TASK
    result: Dict[str, Any] = field(default_factory=dict)
    audit_log: List[AuditEntry] = field(default_factory=list)
    requires_approval: bool = False
    approved_by: str = ""


class AgentGovernor:
    """
    Enforces tool allowlists, URL policies, step limits,
    and audit logging for agent tasks.
    """

    def __init__(
        self,
        allowed_tools: Optional[set] = None,
        max_steps: int = MAX_STEPS_PER_TASK,
    ):
        self.allowed_tools = allowed_tools or ALLOWED_TOOLS
        self.max_steps = max_steps
        self._audit_log: List[AuditEntry] = []

    def check_tool(self, tool_name: str, task: AgentTask) -> bool:
        """Return True if the tool is allowed; log the check."""
        if tool_name in BLOCKED_TOOLS:
            entry = self._log_action(task, tool_name, "blocked", "Tool in blocked list")
            logger.warning(f"Agent tool BLOCKED: {tool_name} (task {task.task_id})")
            return False

        if tool_name not in self.allowed_tools:
            entry = self._log_action(task, tool_name, "blocked", "Tool not in allowlist")
            logger.warning(f"Agent tool NOT ALLOWED: {tool_name} (task {task.task_id})")
            return False

        if task.steps_taken >= task.max_steps:
            entry = self._log_action(task, tool_name, "blocked", "Step limit reached")
            logger.warning(f"Agent step limit reached for task {task.task_id}")
            return False

        return True

    def execute_tool(
        self,
        task: AgentTask,
        tool_name: str,
        tool_fn: Callable,
        input_summary: str = "",
        **kwargs,
    ) -> Optional[Any]:
        """Execute a governed tool call with full audit logging."""
        if not self.check_tool(tool_name, task):
            return None

        task.steps_taken += 1
        try:
            result = tool_fn(**kwargs)
            self._log_action(
                task, tool_name, "allowed",
                input_summary=input_summary,
                output_summary=str(result)[:200] if result else "",
            )
            return result
        except Exception as e:
            self._log_action(
                task, tool_name, "allowed",
                input_summary=input_summary,
                output_summary=f"ERROR: {str(e)[:200]}",
            )
            raise

    def require_approval(self, task: AgentTask, reason: str) -> None:
        """Mark a task as requiring human approval before proceeding."""
        task.requires_approval = True
        task.status = "awaiting_approval"
        self._log_action(
            task, "approval_gate", "requires_approval",
            input_summary=reason,
        )
        logger.info(f"Task {task.task_id} requires approval: {reason}")

    def approve_task(self, task: AgentTask, reviewer: str) -> None:
        """Record approval and allow the task to continue."""
        task.approved_by = reviewer
        task.requires_approval = False
        task.status = "running"
        self._log_action(
            task, "approval_granted", "allowed",
            input_summary=f"Approved by {reviewer}",
        )
        logger.info(f"Task {task.task_id} approved by {reviewer}")

    def _log_action(
        self,
        task: AgentTask,
        tool_name: str,
        status: str,
        input_summary: str = "",
        output_summary: str = "",
    ) -> AuditEntry:
        entry = AuditEntry(
            entry_id=str(uuid.uuid4())[:8],
            task_id=task.task_id,
            tool_name=tool_name,
            timestamp=datetime.now().isoformat(),
            input_summary=input_summary[:500],
            output_summary=output_summary[:500],
            status=status,
        )
        task.audit_log.append(entry)
        self._audit_log.append(entry)
        return entry

    def get_full_audit_log(self) -> List[AuditEntry]:
        return list(self._audit_log)


# ───────────────────────────────────────────────────────────────
# Built-in agent tools (narrow, task-oriented)
# ───────────────────────────────────────────────────────────────

def summarize_events(events: List[CompetitorEvent], max_events: int = 20) -> Dict[str, Any]:
    """Produce a structured summary of recent events."""
    subset = events[:max_events]
    by_competitor: Dict[str, int] = {}
    by_signal: Dict[str, int] = {}
    high_conf = []

    for e in subset:
        by_competitor[e.competitor] = by_competitor.get(e.competitor, 0) + 1
        by_signal[e.signal_type] = by_signal.get(e.signal_type, 0) + 1
        if e.confidence_score >= 0.7:
            high_conf.append({
                "title": e.title,
                "competitor": e.competitor,
                "confidence": e.confidence_score,
            })

    return {
        "total_events": len(subset),
        "by_competitor": by_competitor,
        "by_signal_type": by_signal,
        "high_confidence_events": high_conf[:10],
    }


def build_timeline(events: List[CompetitorEvent]) -> List[Dict[str, str]]:
    """Build a chronological timeline from events."""
    sorted_events = sorted(events, key=lambda e: e.date_detected)
    return [
        {
            "date": e.date_detected[:10],
            "competitor": e.competitor,
            "title": e.title,
            "signal_type": e.signal_type,
            "confidence": f"{e.confidence_score:.2f}",
        }
        for e in sorted_events
    ]


def generate_competitor_brief(
    events: List[CompetitorEvent],
    competitor: str,
) -> Dict[str, Any]:
    """Generate a structured brief for a single competitor."""
    comp_events = [e for e in events if e.competitor == competitor]
    if not comp_events:
        return {"competitor": competitor, "status": "no_events"}

    by_signal = {}
    for e in comp_events:
        by_signal.setdefault(e.signal_type, []).append({
            "title": e.title,
            "confidence": e.confidence_score,
            "date": e.date_detected[:10],
        })

    avg_conf = sum(e.confidence_score for e in comp_events) / len(comp_events)
    high_conf = [e for e in comp_events if e.confidence_score >= 0.7]

    return {
        "competitor": competitor,
        "total_signals": len(comp_events),
        "avg_confidence": round(avg_conf, 2),
        "high_confidence_count": len(high_conf),
        "by_signal_type": by_signal,
        "top_implications": [
            e.strategic_implication for e in sorted(
                comp_events, key=lambda x: x.confidence_score, reverse=True
            )[:5]
        ],
    }


def search_events(
    events: List[CompetitorEvent],
    query: str,
    max_results: int = 20,
) -> List[Dict[str, Any]]:
    """Search events by keyword in title, description, or implication."""
    query_lower = query.lower()
    matches = []
    for e in events:
        searchable = f"{e.title} {e.description} {e.strategic_implication}".lower()
        if query_lower in searchable:
            matches.append({
                "event_id": e.event_id,
                "title": e.title,
                "competitor": e.competitor,
                "confidence": e.confidence_score,
                "signal_type": e.signal_type,
            })
            if len(matches) >= max_results:
                break
    return matches


TOOL_REGISTRY: Dict[str, Callable] = {
    "summarize_events": summarize_events,
    "build_timeline": build_timeline,
    "generate_competitor_brief": generate_competitor_brief,
    "search_events": search_events,
}
