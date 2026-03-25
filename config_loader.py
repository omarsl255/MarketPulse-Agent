"""
config_loader.py — Loads and validates config.yaml + .env secrets.
V3: adds URL validation, alert config, observability config, budget limits.
"""

import os
import re
import yaml
import logging
from pathlib import Path
from ipaddress import ip_address
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URL safety
# ---------------------------------------------------------------------------

_PRIVATE_RANGES = [
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.", "127.", "0.",
]

ALLOWED_SCHEMES = {"https", "http"}


def validate_url(url: str, *, strict: bool = False) -> List[str]:
    """
    Return a list of warnings for a target URL.
    In strict mode, non-https or private-range URLs produce warnings.
    """
    warnings = []
    try:
        parsed = urlparse(url)
    except Exception:
        return [f"Unparseable URL: {url}"]

    if parsed.scheme not in ALLOWED_SCHEMES:
        warnings.append(f"Disallowed scheme '{parsed.scheme}' in {url}")

    if parsed.scheme == "file":
        warnings.append(f"file: scheme blocked for safety: {url}")

    if strict and parsed.scheme != "https":
        warnings.append(f"Non-HTTPS URL: {url}")

    hostname = parsed.hostname or ""
    if hostname in ("localhost", ""):
        warnings.append(f"Localhost or empty hostname in {url}")

    try:
        ip = ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            warnings.append(f"Private/loopback IP in URL: {url}")
    except ValueError:
        for prefix in _PRIVATE_RANGES:
            if hostname.startswith(prefix):
                warnings.append(f"Hostname looks like private IP: {url}")
                break

    if re.search(r"metadata\.google|169\.254\.", url, re.IGNORECASE):
        warnings.append(f"Possible cloud metadata endpoint: {url}")

    return warnings


# ---------------------------------------------------------------------------
# Pydantic config models
# ---------------------------------------------------------------------------

class ProjectConfig(BaseModel):
    name: str = "RivalSense"
    version: str = "0.4.0"
    description: str = ""
    environment: str = "prototype"

class PerspectiveConfig(BaseModel):
    employer: str = "ABB"
    objective: str = ""

class LLMConfig(BaseModel):
    model: str = "gemini-2.5-flash"
    temperature: float = 0
    max_input_chars: int = 15000

class ScheduleConfig(BaseModel):
    interval_hours: int = 24

class CollectorConfig(BaseModel):
    timeout_seconds: int = 15
    max_retries: int = 3
    backoff_factor: int = 2

class CompetitorConfig(BaseModel):
    name: str
    tier: int = 1
    focus_areas: List[str] = Field(default_factory=list)
    urls: Dict[str, List[str]] = Field(default_factory=dict)

class AlertConfig(BaseModel):
    enabled: bool = Field(default=False)
    min_confidence: float = Field(default=0.7, description="Minimum confidence to trigger an alert")
    channels: List[str] = Field(default_factory=lambda: ["log"])
    cooldown_minutes: int = Field(default=60, description="Suppress duplicate alerts within this window")
    max_alerts_per_run: int = Field(default=50)

class ObservabilityConfig(BaseModel):
    enabled: bool = Field(default=True)
    provider: str = Field(default="log", description="log, langfuse, langsmith")
    redact_secrets: bool = Field(default=True)
    redact_raw_text: bool = Field(default=True)
    max_trace_text_chars: int = Field(default=200, description="Truncate text fields in traces")
    environment: str = Field(default="dev", description="dev or prod project separation")

class BudgetConfig(BaseModel):
    max_tokens_per_run: int = Field(default=500_000)
    max_tokens_per_competitor: int = Field(default=200_000)
    max_llm_calls_per_run: int = Field(default=200)
    max_input_chars: int = Field(default=15_000)

class AuthConfig(BaseModel):
    enabled: bool = Field(default=False)
    provider: str = Field(default="none", description="none, reverse_proxy, basic")
    header_name: str = Field(default="X-Forwarded-User", description="Header for reverse-proxy auth")
    allowed_users: List[str] = Field(default_factory=list, description="Usernames allowed when basic auth enabled")

class RetentionConfig(BaseModel):
    events_days: int = Field(default=365, description="Keep events for this many days")
    snapshots_days: int = Field(default=90, description="Keep snapshots for this many days")
    failed_extractions_days: int = Field(default=30)
    alerts_days: int = Field(default=90)
    runs_days: int = Field(default=90)


class AppConfig(BaseModel):
    project: ProjectConfig = ProjectConfig()
    perspective: PerspectiveConfig = PerspectiveConfig()
    competitors: List[CompetitorConfig] = Field(default_factory=list)
    schedule: ScheduleConfig = ScheduleConfig()
    llm: LLMConfig = LLMConfig()
    collector: CollectorConfig = CollectorConfig()
    alerts: AlertConfig = AlertConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    budget: BudgetConfig = BudgetConfig()
    auth: AuthConfig = AuthConfig()
    retention: RetentionConfig = RetentionConfig()

    @property
    def employer(self) -> str:
        return self.perspective.employer

# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent / "config.yaml"
_cached_config: Optional[AppConfig] = None


def load_secrets() -> None:
    """Load secrets from .env file if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info("Loaded secrets from .env")
        else:
            logger.debug(".env file not found — relying on system environment variables")
    except ImportError:
        logger.debug("python-dotenv not installed — relying on system environment variables")

    if not os.environ.get("GOOGLE_API_KEY"):
        logger.warning("GOOGLE_API_KEY is not set. LLM extraction will fail.")


def get_config(config_path: Optional[Path] = None) -> AppConfig:
    """Return the validated application config (cached after first load)."""
    global _cached_config
    if _cached_config is not None and config_path is None:
        return _cached_config

    path = config_path or _CONFIG_PATH
    if not path.exists():
        logger.warning(f"Config file not found at {path} — using defaults")
        _cached_config = AppConfig()
    else:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        _cached_config = AppConfig(**raw)
        logger.info(f"Loaded config from {path} ({len(_cached_config.competitors)} competitors)")

    _validate_all_urls(_cached_config)
    return _cached_config


def _validate_all_urls(config: AppConfig) -> None:
    """Run safety checks on all configured target URLs at load time."""
    strict = config.project.environment != "prototype"
    seen: set = set()
    for comp in config.competitors:
        for signal_type, urls in comp.urls.items():
            for url in urls:
                key = (comp.name, signal_type, url)
                if key in seen:
                    logger.warning(f"Duplicate target: [{comp.name}] [{signal_type}] {url}")
                seen.add(key)

                warnings = validate_url(url, strict=strict)
                for w in warnings:
                    logger.warning(f"URL guardrail: {w}")


def get_all_target_urls(config: Optional[AppConfig] = None) -> list:
    """
    Flatten all competitor URLs into a list of dicts:
    [{"competitor": "Siemens", "signal_type": "developer_api", "url": "https://..."}, ...]
    """
    cfg = config or get_config()
    targets = []
    for comp in cfg.competitors:
        for signal_type, urls in comp.urls.items():
            for url in urls:
                warnings = validate_url(url)
                if any("Disallowed scheme" in w or "file: scheme" in w for w in warnings):
                    logger.error(f"Skipping unsafe URL: {url}")
                    continue
                targets.append({
                    "competitor": comp.name,
                    "signal_type": signal_type,
                    "url": url,
                })
    return targets


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    load_secrets()
    cfg = get_config()
    print(f"Project: {cfg.project.name} v{cfg.project.version}")
    print(f"Employer: {cfg.employer}")
    print(f"Competitors: {[c.name for c in cfg.competitors]}")
    print(f"Alerts enabled: {cfg.alerts.enabled}, channels: {cfg.alerts.channels}")
    print(f"Observability: {cfg.observability.provider}")
    print(f"Auth: {cfg.auth.provider}")
    targets = get_all_target_urls(cfg)
    print(f"Total targets: {len(targets)}")
    for t in targets:
        print(f"  [{t['signal_type']}] {t['competitor']}: {t['url']}")
