"""
notifier.py — Alert routing for V3.
Routes high-confidence events to configured channels (log, Slack, Teams, email).
Secrets come from environment variables, never from config.yaml.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional

import requests

from schema import CompetitorEvent, AlertRecord

logger = logging.getLogger("notifier")


def _get_secret(env_var: str) -> Optional[str]:
    """Retrieve a secret from environment only. Never log the value."""
    val = os.environ.get(env_var)
    if val:
        logger.debug(f"Secret {env_var}: configured=yes")
    else:
        logger.debug(f"Secret {env_var}: configured=no")
    return val


def _build_alert_message(event: CompetitorEvent) -> str:
    """Format an event into a human-readable alert message."""
    return (
        f"[{event.competitor}] {event.title}\n"
        f"Type: {event.event_type} | Signal: {event.signal_type}\n"
        f"Confidence: {event.confidence_score:.2f}\n"
        f"Implication: {event.strategic_implication}\n"
        f"Source: {event.source_url}\n"
        f"Detected: {event.date_detected}"
    )


def _send_log(event: CompetitorEvent) -> AlertRecord:
    """Log the alert locally (always available, no external secrets needed)."""
    msg = _build_alert_message(event)
    logger.info(f"ALERT (log): {msg}")
    return AlertRecord(
        alert_id=str(uuid.uuid4()),
        event_id=event.event_id,
        channel="log",
        status="sent",
        created_at=datetime.now().isoformat(),
        sent_at=datetime.now().isoformat(),
        run_id=event.run_id,
    )


def _send_slack(event: CompetitorEvent) -> AlertRecord:
    """Send alert to Slack via incoming webhook."""
    webhook_url = _get_secret("SLACK_WEBHOOK_URL")
    alert = AlertRecord(
        alert_id=str(uuid.uuid4()),
        event_id=event.event_id,
        channel="slack",
        status="pending",
        created_at=datetime.now().isoformat(),
        run_id=event.run_id,
    )
    if not webhook_url:
        alert.status = "failed"
        alert.error_detail = "SLACK_WEBHOOK_URL not set"
        logger.warning("Slack alert skipped: SLACK_WEBHOOK_URL not configured")
        return alert

    payload = {
        "text": f"*RivalSense Alert*\n{_build_alert_message(event)}",
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        alert.status = "sent"
        alert.sent_at = datetime.now().isoformat()
        logger.info(f"Slack alert sent for event {event.event_id}")
    except Exception as e:
        alert.status = "failed"
        alert.error_detail = str(e)[:300]
        logger.error(f"Slack alert failed: {e}")

    return alert


def _send_teams(event: CompetitorEvent) -> AlertRecord:
    """Send alert to Microsoft Teams via incoming webhook."""
    webhook_url = _get_secret("TEAMS_WEBHOOK_URL")
    alert = AlertRecord(
        alert_id=str(uuid.uuid4()),
        event_id=event.event_id,
        channel="teams",
        status="pending",
        created_at=datetime.now().isoformat(),
        run_id=event.run_id,
    )
    if not webhook_url:
        alert.status = "failed"
        alert.error_detail = "TEAMS_WEBHOOK_URL not set"
        logger.warning("Teams alert skipped: TEAMS_WEBHOOK_URL not configured")
        return alert

    payload = {
        "text": f"**RivalSense Alert**\n\n{_build_alert_message(event)}",
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        alert.status = "sent"
        alert.sent_at = datetime.now().isoformat()
        logger.info(f"Teams alert sent for event {event.event_id}")
    except Exception as e:
        alert.status = "failed"
        alert.error_detail = str(e)[:300]
        logger.error(f"Teams alert failed: {e}")

    return alert


def _send_email(event: CompetitorEvent) -> AlertRecord:
    """Send alert via email (SMTP). Requires SMTP_* env vars."""
    alert = AlertRecord(
        alert_id=str(uuid.uuid4()),
        event_id=event.event_id,
        channel="email",
        status="pending",
        created_at=datetime.now().isoformat(),
        run_id=event.run_id,
    )
    smtp_host = _get_secret("SMTP_HOST")
    smtp_to = _get_secret("ALERT_EMAIL_TO")

    if not smtp_host or not smtp_to:
        alert.status = "failed"
        alert.error_detail = "SMTP_HOST or ALERT_EMAIL_TO not set"
        logger.warning("Email alert skipped: SMTP env vars not configured")
        return alert

    try:
        import smtplib
        from email.mime.text import MIMEText

        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASSWORD", "")
        from_addr = os.environ.get("ALERT_EMAIL_FROM", smtp_user or "rivalsense@alert.local")

        msg = MIMEText(_build_alert_message(event))
        msg["Subject"] = f"RivalSense: [{event.competitor}] {event.title}"
        msg["From"] = from_addr
        msg["To"] = smtp_to

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            if smtp_port == 587:
                server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, [smtp_to], msg.as_string())

        alert.status = "sent"
        alert.sent_at = datetime.now().isoformat()
        logger.info(f"Email alert sent for event {event.event_id}")
    except Exception as e:
        alert.status = "failed"
        alert.error_detail = str(e)[:300]
        logger.error(f"Email alert failed: {e}")

    return alert


_CHANNEL_HANDLERS = {
    "log": _send_log,
    "slack": _send_slack,
    "teams": _send_teams,
    "email": _send_email,
}


def should_alert(event: CompetitorEvent, min_confidence: float = 0.7) -> bool:
    """Determine if an event qualifies for alerting."""
    return event.confidence_score >= min_confidence


def send_alerts(
    events: List[CompetitorEvent],
    channels: List[str],
    min_confidence: float = 0.7,
    max_alerts: int = 50,
) -> List[AlertRecord]:
    """
    Route qualifying events to the configured alert channels.
    Returns a list of AlertRecord for persistence.
    """
    records: List[AlertRecord] = []
    sent_count = 0

    for event in events:
        if sent_count >= max_alerts:
            logger.warning(f"Alert cap reached ({max_alerts}), suppressing remaining")
            break

        if not should_alert(event, min_confidence):
            continue

        for channel in channels:
            handler = _CHANNEL_HANDLERS.get(channel)
            if handler is None:
                logger.warning(f"Unknown alert channel: {channel}")
                continue

            alert = handler(event)
            records.append(alert)
            if alert.status == "sent":
                sent_count += 1

    return records
