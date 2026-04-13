from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery("bidwatch", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_timeout=3,
    broker_connection_retry_on_startup=False,
)

celery.conf.beat_schedule = {
    "collect-public-api-morning": {
        "task": "app.tasks.collect_api.collect_public_api_task",
        "schedule": crontab(hour=8, minute=0),
    },
    "collect-public-api-evening": {
        "task": "app.tasks.collect_api.collect_public_api_task",
        "schedule": crontab(hour=20, minute=0),
    },
    "collect-scrapers-early": {
        "task": "app.tasks.collect_scraper.collect_scrapers_task",
        "schedule": crontab(hour=2, minute=0),
    },
    "collect-scrapers-afternoon": {
        "task": "app.tasks.collect_api.collect_public_api_task",
        "schedule": crontab(hour=14, minute=0),
    },
}

celery.autodiscover_tasks(["app.tasks"])
