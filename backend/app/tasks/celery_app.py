"""Celery application configuration.

Broker/result backend default to the local Redis (Sprint 4 compose stack).
Tests set SENTINEL_CELERY_EAGER=true so tasks execute synchronously with no
broker required. On Windows, run workers with `-P solo`.
"""

from celery import Celery

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

celery_app = Celery(
    "sentinel",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.build_tasks", "app.tasks.rag_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_eager,
    task_eager_propagates=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "nightly-security-scan": {
            "task": "app.tasks.build_tasks.run_security_scan_all",
            "schedule": settings.schedule_interval_minutes * 60,
        }
    },
)

logger.info(
    "Celery configured (broker=%s eager=%s)",
    settings.redis_url,
    settings.celery_eager,
)
