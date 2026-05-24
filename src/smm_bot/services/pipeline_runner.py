from __future__ import annotations

import json
import logging
import time
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot
from sqlalchemy import select

from smm_bot.agents.llm import OpenRouterLLMClient, TrackingLLMClient
from smm_bot.agents.pipeline import PipelineExecutor
from smm_bot.agents.registry import MVP_GRAPH, AgentName, registry_for_quality_mode
from smm_bot.agents.schemas import FinalContentPack
from smm_bot.core.config import get_settings
from smm_bot.db.models import (
    AgentRun,
    FinalContentPack as FinalContentPackRow,
    PipelineError,
    PipelineRun,
    ProjectInput,
)
from smm_bot.db.session import async_session_factory
from smm_bot.services.event_trace import PipelineEventLogger
from smm_bot.services.input_normalizer import normalize_pipeline_input


logger = logging.getLogger(__name__)

TOTAL_AGENTS = len(MVP_GRAPH)

QUALITY_MODE_TITLES = {
    "balanced": "Единый",
}

AGENT_PROGRESS: dict[str, dict[str, str]] = {
    "brief": {
        "emoji": "📋",
        "label": "Анализирую бриф",
        "quip": "Читаю без осуждения...",
    },
    "audience_segmentation": {
        "emoji": "👥",
        "label": "Сегментирую аудиторию",
        "quip": "Делю людей на группы. Без дискриминации.",
    },
    "persona_builder": {
        "emoji": "🎭",
        "label": "Строю персоны",
        "quip": "Создаю воображаемых друзей для маркетинга...",
    },
    "pain_trigger": {
        "emoji": "💊",
        "label": "Ищу боли и триггеры",
        "quip": "Копаю в психологию. Это не больно, обещаю.",
    },
    "context_auditor": {
        "emoji": "🧭",
        "label": "Проверяю контекст",
        "quip": "Сверяю, не уехал ли смысл проекта в сторону.",
    },
    "positioning": {
        "emoji": "🎯",
        "label": "Разрабатываю позиционирование",
        "quip": "Думаю как выделиться среди всего этого шума...",
    },
    "content_strategy": {
        "emoji": "📊",
        "label": "Формирую контент-стратегию",
        "quip": "Строю план. Как военный, но для лайков.",
    },
    "rubricator": {
        "emoji": "📁",
        "label": "Создаю рубрики",
        "quip": "Раскладываю контент по полочкам...",
    },
    "pain_based_generator": {
        "emoji": "🔥",
        "label": "Генерирую идеи на боли",
        "quip": "Придумываю острый контент. Да, это больно.",
    },
    "trigger_based_generator": {
        "emoji": "⚡",
        "label": "Генерирую идеи на триггеры",
        "quip": "Ищу вирусные зацепки...",
    },
    "funnel_based_generator": {
        "emoji": "🎪",
        "label": "Генерирую идеи по воронке",
        "quip": "Выстраиваю путь от «кто ты» до «берём».",
    },
    "deduplication": {
        "emoji": "🔄",
        "label": "Убираю дубли",
        "quip": "Сравниваю идеи. Одинаковые — в утиль.",
    },
    "idea_critic": {
        "emoji": "🧐",
        "label": "Критикую идеи",
        "quip": "Безжалостно смотрю что реально сработает...",
    },
    "garbage_filter": {
        "emoji": "🗑️",
        "label": "Выкидываю мусор",
        "quip": "Убираю слабые идеи. Жалости нет.",
    },
    "idea_improver": {
        "emoji": "🔧",
        "label": "Улучшаю идеи",
        "quip": "Чиню почти хорошие — чтобы стали реально хорошими.",
    },
    "reference_video_researcher": {
        "emoji": "🔎",
        "label": "Подбираю видео-паттерны",
        "quip": "Ищу рабочую форму для похожих сегментов.",
    },
    "topic_angle_generator": {
        "emoji": "🧩",
        "label": "Выбираю углы подачи",
        "quip": "Ищу, под каким углом идея будет цеплять.",
    },
    "hook_generator": {
        "emoji": "🎣",
        "label": "Генерирую хуки",
        "quip": "Первые секунды решают многое.",
    },
    "script_writer": {
        "emoji": "✍️",
        "label": "Пишу сценарии",
        "quip": "Создаю реальный контент. Скоро...",
    },
    "retention_optimizer": {
        "emoji": "📈",
        "label": "Проверяю удержание",
        "quip": "Смотрю, где зритель может пролистнуть дальше.",
    },
    "script_critic": {
        "emoji": "🎬",
        "label": "Редактирую сценарии",
        "quip": "Шлифую финальный вариант...",
    },
    "blind_script_checker": {
        "emoji": "🕵️",
        "label": "Проверяю смысл сценариев",
        "quip": "Читаю сценарии вслепую и сверяю с бизнесом.",
    },
    "final_content_pack": {
        "emoji": "📦",
        "label": "Собираю контент-пак",
        "quip": "Упаковываю результат. Уже почти!",
    },
}


def _progress_bar(current: int, total: int, width: int = 16) -> str:
    filled = int(width * current / total)
    return "█" * filled + "░" * (width - filled)


def _elapsed_str(start: datetime) -> str:
    secs = int((datetime.now(UTC) - start).total_seconds())
    return f"{secs // 60}:{secs % 60:02d}"


def _edit_telegram_message_sync(
    bot_token: str,
    chat_id: int,
    message_id: int,
    text: str,
    keyboard: list | None = None,
    *,
    attempts: int = 1,
) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload_data: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if keyboard is not None:
        payload_data["reply_markup"] = {"inline_keyboard": keyboard}
    payload = json.dumps(payload_data).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            return True
        except Exception as exc:
            if attempt >= attempts:
                logger.debug("[telegram] message edit skipped: %s", exc)
                return False
            time.sleep(1)
    return False


def _make_progress_callback(
    bot_token: str,
    chat_id: int,
    message_id: int,
    quality_mode: str,
    start_time: datetime,
) -> Callable[[str], None]:
    step_counter = [0]

    def on_agent_start(agent_name: AgentName) -> None:
        step_counter[0] += 1
        step = step_counter[0]
        info = AGENT_PROGRESS.get(agent_name, {"emoji": "⚙️", "label": agent_name, "quip": ""})
        bar = _progress_bar(step - 1, TOTAL_AGENTS)
        text = (
            f"⚙️ Генерирую контент-пак\n\n"
            f"[{bar}] {step}/{TOTAL_AGENTS}\n\n"
            f"{info['emoji']} {info['label']}\n"
            f"   {info['quip']}\n\n"
            f"⏱ {_elapsed_str(start_time)}"
        )
        logger.debug("[progress] step %d/%d — %s", step, TOTAL_AGENTS, agent_name)
        _edit_telegram_message_sync(bot_token, chat_id, message_id, text)

    return on_agent_start


FUNNEL_LABELS = {
    "awareness": "Охват",
    "trust": "Доверие",
    "conversion": "Продажа",
    "retention": "Удержание",
}


def format_content_page(content: dict, page: int, total: int) -> str:
    title = content.get("title") or content.get("idea_id") or "Сценарий"
    persona = content.get("target_persona", "")
    pain = content.get("pain", "")
    trigger = content.get("trigger", "")
    funnel = FUNNEL_LABELS.get(content.get("funnel_stage", ""), "")
    rubric = content.get("rubric", "")
    why = content.get("why_approved", "")
    score = content.get("quality_score") or 0

    script = content.get("script") or {}
    hook = script.get("hook", "")
    scenes = script.get("scene_by_scene") or []
    cta = script.get("cta", "")
    caption = script.get("caption", "")
    shooting = script.get("shooting_notes", "")
    duration = script.get("duration", "")

    lines: list[str] = [f"📹 Сценарий {page + 1} из {total}", "", f"🎬 {title}", ""]

    meta = []
    if persona:
        meta.append(f"👤 {persona}")
    if pain:
        meta.append(f"💊 {pain}")
    if trigger:
        meta.append(f"⚡ {trigger}")
    if funnel:
        meta.append(f"📊 {funnel}")
    if rubric:
        meta.append(f"📁 {rubric}")
    if duration:
        meta.append(f"⏱ {duration}")
    if score:
        meta.append(f"⭐ {score:.1f}/5")
    lines.extend(meta)

    if hook:
        lines += ["", "🎣 Хук:", hook]

    if scenes:
        lines += ["", "🎬 Сценарий:"]
        for i, scene in enumerate(scenes, 1):
            time_ = scene.get("time", "")
            visual = scene.get("visual", "")
            voice = scene.get("voiceover", "")
            text_on = scene.get("text_on_screen", "")
            header = f"  [{i}]" + (f" {time_}" if time_ else "")
            lines.append(header)
            if visual:
                lines.append(f"  👁 {visual}")
            if voice:
                lines.append(f"  🎙 {voice}")
            if text_on:
                lines.append(f"  💬 {text_on}")

    if cta:
        lines += ["", f"📢 CTA: {cta}"]
    if caption:
        lines += ["", "📝 Подпись для публикации:", caption]
    if shooting:
        lines += ["", f"🎥 Съёмка: {shooting}"]
    if why:
        lines += ["", f"✅ Почему одобрено: {why}"]

    text = "\n".join(lines)
    return text[:4000] + "\n…" if len(text) > 4000 else text


def _nav_keyboard_json(run_id: str, page: int, total: int) -> list:
    nav = []
    if page > 0:
        nav.append({"text": "◀️", "callback_data": f"content:nav:{run_id}:{page - 1}"})
    nav.append({"text": f"{page + 1}/{total}", "callback_data": "content:noop"})
    if page < total - 1:
        nav.append({"text": "▶️", "callback_data": f"content:nav:{run_id}:{page + 1}"})
    return [nav, [{"text": "⬅️ Меню", "callback_data": "menu:home"}]]


def _send_with_keyboard_sync(
    bot_token: str,
    chat_id: int,
    text: str,
    keyboard: list,
    *,
    attempts: int = 1,
) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {"inline_keyboard": keyboard},
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            return True
        except Exception as exc:
            if attempt >= attempts:
                logger.warning("[telegram] send with keyboard failed: %s", exc)
                return False
            time.sleep(1)
    return False


async def execute_pipeline_run(
    pipeline_run_id: str,
    *,
    telegram_chat_id: int | None = None,
    telegram_message_id: int | None = None,
) -> None:
    run_uuid = uuid.UUID(pipeline_run_id)
    settings = get_settings()

    logger.info("[pipeline] starting run=%s", run_uuid)

    async with async_session_factory() as session:
        run = await session.get(PipelineRun, run_uuid)
        if run is None:
            raise RuntimeError(f"Pipeline run {run_uuid} not found")

        project_input = None
        if run.project_input_id is not None:
            project_input = await session.get(ProjectInput, run.project_input_id)
        if project_input is None:
            raise RuntimeError(f"Project input for pipeline run {run_uuid} not found")

        input_metadata = dict(project_input.metadata_ or {})
        normalized_input = normalize_pipeline_input(
            raw_text=project_input.raw_text,
            platform=project_input.platform,
            content_goal=project_input.content_goal,
            quality_mode=run.quality_mode,
            ideas_count=project_input.ideas_count,
            scripts_count=project_input.scripts_count,
            source=input_metadata.get("source", "telegram_bot"),
            telegram_user_id=input_metadata.get("telegram_user_id"),
            telegram_username=input_metadata.get("telegram_username"),
            telegram_chat_id=input_metadata.get("telegram_chat_id"),
            telegram_message_id=input_metadata.get("telegram_message_id"),
        )
        trace_logger = PipelineEventLogger(run_id=run_uuid, trace_dir=settings.pipeline_trace_dir)
        input_metadata["normalized_input"] = normalized_input.model_dump()
        input_metadata["trace_file"] = str(trace_logger.path)
        project_input.metadata_ = input_metadata

        run.status = "running"
        run.started_at = datetime.now(UTC)
        run.current_agent = "brief"
        run.error_message = None
        await session.commit()

    logger.info(
        "[pipeline] run=%s  mode=%s  platform=%s  input_len=%d",
        run_uuid,
        run.quality_mode,
        project_input.platform,
        len(project_input.raw_text),
    )
    logger.info("[pipeline] trace file run=%s path=%s", run_uuid, trace_logger.path)
    trace_logger.record(
        "pipeline_run_loaded",
        quality_mode=run.quality_mode,
        project_input_id=str(project_input.id),
        project_id=str(project_input.project_id),
        normalized_input=normalized_input,
    )

    start_time = datetime.now(UTC)
    t_start = time.monotonic()

    progress_callback: Callable[[str], None] | None = None
    if (
        telegram_chat_id is not None
        and telegram_message_id is not None
        and settings.telegram_bot_token
    ):
        progress_callback = _make_progress_callback(
            settings.telegram_bot_token,
            telegram_chat_id,
            telegram_message_id,
            run.quality_mode,
            start_time,
        )

    try:
        registry = registry_for_quality_mode(run.quality_mode)
        llm_client = TrackingLLMClient(
            OpenRouterLLMClient(api_key=settings.open_router_key, raise_on_failure=True)
        )
        result = PipelineExecutor(
            llm_client,
            registry=registry,
            on_agent_start=progress_callback,
            on_agent_event=lambda event: _record_trace_event(trace_logger, event),
        ).run(
            normalized_input.to_company_input()
        )
        pack = result.final_content_pack.final_content_pack
        trace_logger.record(
            "pipeline_result",
            outputs=result.outputs,
            final_content_pack=pack,
            approved_count=len(pack.approved_content),
            rejected_count=len(pack.rejected_content),
        )

        async with async_session_factory() as session:
            run = await session.get(PipelineRun, run_uuid)
            if run is None:
                raise RuntimeError(f"Pipeline run {run_uuid} disappeared")

            await _save_agent_runs(session, run, result.outputs, registry)
            await _save_final_pack(session, run, pack)

            run.status = "completed"
            run.current_agent = "final_content_pack"
            run.finished_at = datetime.now(UTC)
            await session.commit()

        elapsed = time.monotonic() - t_start
        logger.info(
            "[pipeline] ✓ completed  run=%s  approved=%d  rejected=%d  elapsed=%.1fs",
            run_uuid,
            len(pack.approved_content),
            len(pack.rejected_content),
            elapsed,
        )
        trace_logger.record(
            "pipeline_completed",
            elapsed_seconds=elapsed,
            approved_count=len(pack.approved_content),
            rejected_count=len(pack.rejected_content),
        )

        if telegram_chat_id is not None and settings.telegram_bot_token:
            approved_list = [item.model_dump() for item in pack.approved_content]
            total = len(approved_list)

            if total > 0:
                first_page = format_content_page(approved_list[0], 0, total)
                keyboard = _nav_keyboard_json(str(run_uuid), 0, total)
                delivered = False
                if telegram_message_id is not None:
                    delivered = _edit_telegram_message_sync(
                        settings.telegram_bot_token,
                        telegram_chat_id,
                        telegram_message_id,
                        first_page,
                        keyboard,
                        attempts=3,
                    )
                if not delivered:
                    delivered = _send_with_keyboard_sync(
                        settings.telegram_bot_token,
                        telegram_chat_id,
                        first_page,
                        keyboard,
                        attempts=3,
                    )
                if not delivered:
                    logger.error("[telegram] final content delivery failed  run=%s", run_uuid)
                    trace_logger.record("telegram_delivery_failed", approved_count=total)
            else:
                summary = (
                    "⚠️ Генерация завершена, но финальные сценарии не сформировались.\n\n"
                    f"Run ID: {run_uuid}\n"
                    "Попробуйте запустить снова с более подробными вводными или проверьте статус запуска."
                )
                delivered = False
                if telegram_message_id is not None:
                    delivered = _edit_telegram_message_sync(
                        settings.telegram_bot_token,
                        telegram_chat_id,
                        telegram_message_id,
                        summary,
                        attempts=3,
                    )
                if not delivered:
                    await _send_telegram_message(telegram_chat_id, summary)

    except Exception as exc:
        elapsed = time.monotonic() - t_start
        logger.error(
            "[pipeline] ✗ failed  run=%s  error=%s: %s  elapsed=%.1fs",
            run_uuid,
            type(exc).__name__,
            exc,
            elapsed,
        )
        trace_logger.record(
            "pipeline_failed",
            elapsed_seconds=elapsed,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

        async with async_session_factory() as session:
            run = await session.get(PipelineRun, run_uuid)
            if run is not None:
                run.status = "failed"
                run.finished_at = datetime.now(UTC)
                run.error_message = str(exc)
                session.add(
                    PipelineError(
                        pipeline_run_id=run.id,
                        project_id=run.project_id,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        input_snapshot={"pipeline_run_id": str(run.id)},
                        is_recoverable=True,
                    )
                )
                await session.commit()

        if telegram_chat_id is not None:
            error_text = (
                "❌ Генерация не завершилась.\n\n"
                f"Run ID: {run_uuid}\n"
                f"Ошибка: {type(exc).__name__}: {exc}"
            )
            if telegram_message_id is not None and settings.telegram_bot_token:
                _edit_telegram_message_sync(
                    settings.telegram_bot_token, telegram_chat_id, telegram_message_id, error_text
                )
            else:
                await _send_telegram_message(telegram_chat_id, error_text)
        raise


async def get_run_status_text(pipeline_run_id: str) -> str:
    run_uuid = uuid.UUID(pipeline_run_id)
    async with async_session_factory() as session:
        run = await session.get(PipelineRun, run_uuid)
        if run is None:
            return "Запуск не найден."

        statement = select(FinalContentPackRow).where(
            FinalContentPackRow.pipeline_run_id == run_uuid
        )
        final_pack = await session.scalar(statement)
        project_input = None
        if run.project_input_id is not None:
            project_input = await session.get(ProjectInput, run.project_input_id)

        text = (
            "Статус запуска\n\n"
            f"Run ID: {run.id}\n"
            f"Статус: {run.status}\n"
            "Режим: единый\n"
        )
        if run.current_agent:
            text += f"Текущий агент: {run.current_agent}\n"
        if run.error_message:
            text += f"\nОшибка: {run.error_message}\n"
        if project_input is not None:
            trace_file = (project_input.metadata_ or {}).get("trace_file")
            if trace_file:
                text += f"Trace file: {trace_file}\n"
        if final_pack is not None:
            approved = final_pack.approved_content[:5]
            lines = [
                f"- {item.get('title') or item.get('idea_id') or 'Контент-идея'}"
                for item in approved
            ]
            text += "\nСохраненные идеи:\n" + ("\n".join(lines) or "- Список пуст")
        return text


def _record_trace_event(trace_logger: PipelineEventLogger, event: dict[str, Any]) -> None:
    event = dict(event)
    event_type = event.pop("event_type", "agent_event")
    trace_logger.record(event_type, **event)


async def _save_agent_runs(
    session: Any,
    run: PipelineRun,
    outputs: dict[str, Any],
    registry: Any,
) -> None:
    for agent_order, agent_name in enumerate(MVP_GRAPH, start=1):
        spec = registry[agent_name]
        output_json = outputs.get(agent_name) or {}
        session.add(
            AgentRun(
                pipeline_run_id=run.id,
                project_id=run.project_id,
                agent_name=agent_name,
                agent_order=agent_order,
                status="completed",
                input_json={
                    "project_input_id": str(run.project_input_id),
                    "quality_mode": run.quality_mode,
                },
                output_json=output_json,
                model_id=spec.primary_model,
                temperature=spec.temperature,
                started_at=run.started_at,
                finished_at=datetime.now(UTC),
                validation_status="valid",
            )
        )


async def _save_final_pack(
    session: Any,
    run: PipelineRun,
    pack: FinalContentPack,
) -> None:
    pack_json = pack.model_dump()
    session.add(
        FinalContentPackRow(
            pipeline_run_id=run.id,
            project_id=run.project_id,
            title="AI SMM Content Pack",
            brand_summary=pack.brand_summary.model_dump(),
            audience_summary=pack.audience_summary.model_dump(),
            content_strategy_summary=pack.content_strategy_summary.model_dump(),
            approved_content=[
                item.model_dump() for item in pack.approved_content
            ],
            rejected_content=[
                item.model_dump() for item in pack.rejected_content
            ],
            publishing_recommendations=pack.publishing_recommendations,
            risk_notes=pack.risk_notes,
            next_steps_for_human=pack.next_steps_for_human,
            full_pack_json=pack_json,
        )
    )


async def _send_telegram_message(chat_id: int, text: str) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        return

    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    finally:
        await bot.session.close()
