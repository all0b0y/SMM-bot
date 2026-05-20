from __future__ import annotations

import asyncio
import logging

from smm_bot.services.pipeline_runner import execute_pipeline_run
from smm_bot.worker import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="smm_bot.pipeline.run")
def run_pipeline_task(
    pipeline_run_id: str,
    telegram_chat_id: int | None = None,
    telegram_message_id: int | None = None,
) -> None:
    logger.info(
        "[task] received  run=%s  chat=%s  msg=%s",
        pipeline_run_id,
        telegram_chat_id,
        telegram_message_id,
    )
    try:
        asyncio.run(
            execute_pipeline_run(
                pipeline_run_id,
                telegram_chat_id=telegram_chat_id,
                telegram_message_id=telegram_message_id,
            )
        )
        logger.info("[task] done  run=%s", pipeline_run_id)
    except Exception as exc:
        logger.error("[task] failed  run=%s: %s", pipeline_run_id, exc)
        raise
