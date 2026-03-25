"""
scheduler.py — Runs the intelligence pipeline on a configurable schedule.
Uses APScheduler for recurring execution.
V3: passes trigger='scheduler' to run_pipeline for run metadata.
"""

import logging
import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from config_loader import load_secrets, get_config
from main import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")


def start_scheduler():
    """Start the scheduled pipeline loop."""
    load_secrets()
    config = get_config()
    interval = config.schedule.interval_hours

    scheduler = BlockingScheduler()

    logger.info("Running initial pipeline execution...")
    try:
        run_pipeline(trigger="scheduler")
    except Exception as e:
        logger.error(f"Initial run failed: {e}")

    scheduler.add_job(
        lambda: run_pipeline(trigger="scheduler"),
        "interval",
        hours=interval,
        id="intel_pipeline",
        name=f"Intelligence Pipeline (every {interval}h)",
    )

    def shutdown(signum, frame):
        logger.info("Shutdown signal received — stopping scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(f"Scheduler started — pipeline will run every {interval} hour(s)")
    logger.info("Press Ctrl+C to stop")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    start_scheduler()
