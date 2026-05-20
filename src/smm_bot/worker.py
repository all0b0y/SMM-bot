from celery import Celery

from smm_bot.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "smm_bot",
    broker=str(settings.celery_broker_url),
    backend=str(settings.celery_result_backend),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

import smm_bot.tasks.pipeline  # noqa: E402,F401
