"""
config_loader.py — Loads and validates config.yaml + .env secrets.
"""

import os
import yaml
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic config models
# ---------------------------------------------------------------------------

class ProjectConfig(BaseModel):
    name: str = "RivalSense"
    version: str = "0.3.0"
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

class AppConfig(BaseModel):
    project: ProjectConfig = ProjectConfig()
    perspective: PerspectiveConfig = PerspectiveConfig()
    competitors: List[CompetitorConfig] = Field(default_factory=list)
    schedule: ScheduleConfig = ScheduleConfig()
    llm: LLMConfig = LLMConfig()
    collector: CollectorConfig = CollectorConfig()

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

    # Warn if critical keys are missing
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

    return _cached_config


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
    targets = get_all_target_urls(cfg)
    print(f"Total targets: {len(targets)}")
    for t in targets:
        print(f"  [{t['signal_type']}] {t['competitor']}: {t['url']}")
