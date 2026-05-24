from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from smm_bot.agents.registry import MVP_GRAPH
from smm_bot.agents.schemas import BriefOutput
from smm_bot.db.models import (
    FinalContentPack as FinalContentPackRow,
    PipelineRun,
    Project,
    User,
)
from smm_bot.db.session import async_session_factory
from smm_bot.repositories.pipeline_runs import PipelineRunRepository
from smm_bot.repositories.projects import ProjectInputRepository, ProjectRepository
from smm_bot.repositories.users import UserRepository
from smm_bot.services.brief_questions import format_brief_questions
from smm_bot.services.pipeline_runner import format_content_page, get_run_status_text
from smm_bot.services.input_normalizer import MIN_DESCRIPTION_CHARS, normalize_pipeline_input
from smm_bot.tasks.pipeline import run_pipeline_task


logger = logging.getLogger(__name__)

router = Router(name="smm_bot")

TOTAL_AGENTS = len(MVP_GRAPH)


@dataclass
class BotUserSettings:
    quality_mode: str = "balanced"
    platform: str = "Instagram Reels"
    ideas_count: int = 15   # per generator; 3 generators → 45 ideas total before dedup
    scripts_count: int = 5


USER_SETTINGS: dict[int, BotUserSettings] = {}
LAST_DESCRIPTION: dict[int, str] = {}
CLARIFIED_DESCRIPTION: dict[int, str] = {}
AWAITING_CLARIFICATION: set[int] = set()
# {user_id: (run_id, page_index, script_dict)} — ждём текст для доработки
AWAITING_REFINEMENT: dict[int, tuple[str, int, dict]] = {}


QUALITY_MODES = {
    "balanced": {
        "title": "Единый режим",
        "description": "Одна стабильная модельная политика для всех запусков.",
        "models": [
            "Маркетинговый анализ и проверки: openrouter/owl-alpha",
            "Структурные и лёгкие задачи: deepseek/deepseek-v4-flash",
            "Креатив, идеи и сценарии: deepseek/deepseek-v4-pro",
        ],
    },
}


def get_settings(user_id: int) -> BotUserSettings:
    return USER_SETTINGS.setdefault(user_id, BotUserSettings())


def _clear_user_project_state(user_id: int) -> None:
    LAST_DESCRIPTION.pop(user_id, None)
    CLARIFIED_DESCRIPTION.pop(user_id, None)
    AWAITING_CLARIFICATION.discard(user_id)
    AWAITING_REFINEMENT.pop(user_id, None)


async def _safe_callback_answer(
    callback: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> None:
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as exc:
        logger.debug("[bot] callback answer skipped  user=%s: %s", callback.from_user.id, exc)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Старт проекта", callback_data="menu:start"),
                InlineKeyboardButton(text="📋 Что нужно", callback_data="menu:requirements"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"),
            ],
        ]
    )


def settings_keyboard(selected_mode: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🤖 Модельная политика", callback_data="menu:models")],
            [
                InlineKeyboardButton(text="📋 Что нужно", callback_data="menu:requirements"),
                InlineKeyboardButton(text="⬅️ Меню", callback_data="menu:home"),
            ],
        ]
    )


def start_project_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Запустить генерацию", callback_data="project:run")],
            [InlineKeyboardButton(text="💬 Уточнить детали (лучше результат)", callback_data="project:clarify")],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"),
                InlineKeyboardButton(text="📋 Что нужно", callback_data="menu:requirements"),
            ],
        ]
    )


def content_nav_keyboard(run_id: str, page: int, total: int) -> InlineKeyboardMarkup:
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"content:nav:{run_id}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total}", callback_data="content:noop"))
    if page < total - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"content:nav:{run_id}:{page + 1}"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            nav,
            [
                InlineKeyboardButton(text="✅ Выбрать этот", callback_data=f"content:select:{run_id}:{page}"),
                InlineKeyboardButton(text="✍️ Доработать", callback_data=f"content:refine:{run_id}:{page}"),
            ],
            [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu:home")],
        ]
    )


def selected_script_keyboard(run_id: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Уточнить доработку", callback_data=f"content:refine:{run_id}:{page}")],
            [InlineKeyboardButton(text="◀️ Назад к списку", callback_data=f"content:nav:{run_id}:{page}")],
            [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu:home")],
        ]
    )


def refined_script_keyboard(run_id: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Доработать ещё раз", callback_data=f"content:refine:{run_id}:{page}")],
            [InlineKeyboardButton(text="◀️ Назад к списку", callback_data=f"content:nav:{run_id}:{page}")],
        ]
    )


def _run_script_refiner(script_dict: dict, user_feedback: str, brief_dict: dict, positioning_dict: dict) -> dict:
    """Sync: run script_refiner agent and return refined VideoScript as dict."""
    import json as _json
    from smm_bot.agents.llm import OpenRouterLLMClient
    from smm_bot.agents.prompts import render_prompt
    from smm_bot.agents.registry import MVP_AGENT_REGISTRY
    from smm_bot.agents.schemas import ScriptRefinerOutput
    from smm_bot.core.config import get_settings as get_app_settings

    cfg = get_app_settings()
    llm = OpenRouterLLMClient(api_key=cfg.open_router_key, raise_on_failure=False)
    agent = MVP_AGENT_REGISTRY["script_refiner"]
    prompt = render_prompt("script_refiner", {
        "original_script_json": script_dict,
        "user_feedback": user_feedback,
        "brief_json": brief_dict,
        "positioning_json": positioning_dict,
    })
    result = llm.complete(agent=agent, user_prompt=prompt, output_schema=ScriptRefinerOutput)
    return result.refined_script.model_dump()


def _run_brief_get_questions(description: str, max_questions: int = 10) -> str:
    """Sync: run brief agent and return formatted questions from missing_data."""
    from smm_bot.agents.llm import OpenRouterLLMClient
    from smm_bot.agents.prompts import render_prompt
    from smm_bot.agents.registry import MVP_AGENT_REGISTRY
    from smm_bot.core.config import get_settings as get_app_settings

    cfg = get_app_settings()
    llm = OpenRouterLLMClient(api_key=cfg.open_router_key, raise_on_failure=False)
    agent = MVP_AGENT_REGISTRY["brief"]
    prompt = render_prompt("brief", {"company_description": description})
    brief = llm.complete(agent=agent, user_prompt=prompt, output_schema=BriefOutput)

    return format_brief_questions(brief, max_questions=max_questions)


def clarification_ready_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Запустить с уточнениями", callback_data="project:run")],
        ]
    )


def run_status_keyboard(run_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Проверить статус", callback_data=f"run:status:{run_id}")],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"),
                InlineKeyboardButton(text="⬅️ Меню", callback_data="menu:home"),
            ],
        ]
    )


def welcome_text() -> str:
    return (
        "Привет! Я InsideForU, AI SMM-ассистент для коротких видео.\n\n"
        "Я помогу превратить описание бизнеса, бренда или блога в понятный контент-пак:\n"
        "• анализ аудитории;\n"
        "• боли, желания и триггеры;\n"
        "• контентные направления;\n"
        "• идеи Reels / Shorts / TikTok / VK Клипов;\n"
        "• сценарии с хуком, пользой и CTA;\n"
        "• список слабых идей, которые система отбраковала.\n\n"
        "Нажмите «Старт проекта» или просто отправьте описание бизнеса одним сообщением."
    )


def requirements_text() -> str:
    return (
        "Что нужно для хорошего запуска:\n\n"
        "1. Чем занимается компания, эксперт, бренд или блог.\n"
        "2. Какой продукт, услуга или тема продвигается.\n"
        "3. Для кого это: аудитория, сегменты, география.\n"
        "4. Цель: охваты, доверие, заявки, продажи, удержание.\n"
        "5. Площадка: Instagram Reels, TikTok, YouTube Shorts, VK Клипы, Telegram.\n"
        "6. Tone of voice: экспертный, дружелюбный, премиальный, дерзкий, спокойный.\n"
        "7. Ограничения: что нельзя обещать, какие темы не трогать.\n\n"
        "Можно прислать неидеальный текст. Если данных не хватит, система сделает осторожные "
        "гипотезы и пометит их отдельно."
    )


def settings_text(settings: BotUserSettings) -> str:
    return (
        "Настройки бота\n\n"
        "Режим генерации: единый\n"
        f"Площадка: {settings.platform}\n"
        f"Идей: {settings.ideas_count}\n"
        f"Сценариев: {settings.scripts_count}\n\n"
        "Выбор тарифов отключён: все запуски используют одну модельную политику."
    )


def models_text(settings: BotUserSettings) -> str:
    mode = QUALITY_MODES["balanced"]
    lines = [f"{mode['title']}\n", mode["description"]]
    lines.extend(f"• {model}" for model in mode["models"])
    return "\n".join(lines).strip()


def accepted_description_text(settings: BotUserSettings) -> str:
    total_ideas = settings.ideas_count * 3
    return (
        "Отлично, вводные приняты.\n\n"
        "Я вижу базу для SMM-разбора. Перед запуском можно изменить настройки или сразу "
        "нажать кнопку генерации.\n\n"
        "Режим: единый\n"
        f"Площадка: {settings.platform}\n"
        f"Идей (3 генератора × {settings.ideas_count}): ~{total_ideas}\n"
        f"Финальных сценариев: {settings.scripts_count} лучших"
    )


def initial_loading_text() -> str:
    bar = "░" * 16
    return (
        f"⚙️ Генерирую контент-пак\n\n"
        f"[{bar}] 0/{TOTAL_AGENTS}\n\n"
        f"🚀 Запускаю агентов...\n"
        f"   Разогреваю нейроны, подождите...\n\n"
        f"⏱ 0:00"
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    logger.info("[bot] /start  user=%s", message.from_user.id)
    _clear_user_project_state(message.from_user.id)
    await message.answer(welcome_text(), reply_markup=main_menu_keyboard())


@router.message(Command("menu"))
async def menu_command(message: Message) -> None:
    logger.info("[bot] /menu  user=%s", message.from_user.id)
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    logger.info("[bot] /help  user=%s", message.from_user.id)
    await message.answer(requirements_text(), reply_markup=main_menu_keyboard())


@router.message(Command("last"))
async def last_result_command(message: Message) -> None:
    logger.info("[bot] /last  user=%s", message.from_user.id)
    async with async_session_factory() as session:
        statement = (
            select(FinalContentPackRow, PipelineRun.id)
            .join(PipelineRun, FinalContentPackRow.pipeline_run_id == PipelineRun.id)
            .join(Project, PipelineRun.project_id == Project.id)
            .join(User, Project.user_id == User.id)
            .where(User.telegram_user_id == message.from_user.id)
            .where(PipelineRun.status == "completed")
            .order_by(PipelineRun.finished_at.desc())
            .limit(1)
        )
        row = (await session.execute(statement)).first()

    if row is None:
        await message.answer(
            "Пока нет готовых запусков. Пришлите описание бизнеса и запустите генерацию.",
            reply_markup=main_menu_keyboard(),
        )
        return

    pack_row, run_id = row
    approved = pack_row.approved_content or []
    if not approved:
        await message.answer(
            f"Последний запуск найден, но финальные сценарии пустые.\n\nRun ID: {run_id}",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        format_content_page(approved[0], 0, len(approved)),
        reply_markup=content_nav_keyboard(str(run_id), 0, len(approved)),
    )


@router.message(Command("settings"))
async def settings_command(message: Message) -> None:
    logger.info("[bot] /settings  user=%s", message.from_user.id)
    settings = get_settings(message.from_user.id)
    await message.answer(settings_text(settings), reply_markup=settings_keyboard(settings.quality_mode))


@router.callback_query(F.data == "menu:home")
async def home_callback(callback: CallbackQuery) -> None:
    logger.debug("[bot] callback=menu:home  user=%s", callback.from_user.id)
    await callback.message.answer(welcome_text(), reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:start")
async def start_project_callback(callback: CallbackQuery) -> None:
    logger.debug("[bot] callback=menu:start  user=%s", callback.from_user.id)
    _clear_user_project_state(callback.from_user.id)
    await callback.message.answer(
        "Стартуем. Пришлите описание бизнеса одним сообщением.\n\n"
        "Чем подробнее вводные, тем точнее будут сегменты, боли, идеи и сценарии.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:requirements")
async def requirements_callback(callback: CallbackQuery) -> None:
    logger.debug("[bot] callback=menu:requirements  user=%s", callback.from_user.id)
    await callback.message.answer(requirements_text(), reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:settings")
async def settings_callback(callback: CallbackQuery) -> None:
    logger.debug("[bot] callback=menu:settings  user=%s", callback.from_user.id)
    settings = get_settings(callback.from_user.id)
    await callback.message.answer(
        settings_text(settings),
        reply_markup=settings_keyboard(settings.quality_mode),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:models")
async def models_callback(callback: CallbackQuery) -> None:
    logger.debug("[bot] callback=menu:models  user=%s", callback.from_user.id)
    settings = get_settings(callback.from_user.id)
    await callback.message.answer(models_text(settings), reply_markup=settings_keyboard(settings.quality_mode))
    await callback.answer()


@router.callback_query(F.data.startswith("settings:mode:"))
async def set_quality_mode_callback(callback: CallbackQuery) -> None:
    settings = get_settings(callback.from_user.id)
    settings.quality_mode = "balanced"
    logger.info("[bot] deprecated mode callback ignored  user=%s", callback.from_user.id)
    await callback.message.answer(
        "Выбор режимов отключён. Используется единая модельная политика.",
        reply_markup=settings_keyboard(settings.quality_mode),
    )
    await callback.answer()


@router.callback_query(F.data == "project:clarify")
async def clarify_callback(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    description = LAST_DESCRIPTION.get(user_id)
    if not description:
        await callback.answer("Сначала пришлите описание бизнеса.", show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.answer("🔍 Анализирую описание, формулирую вопросы...")
    logger.info("[bot] brief analysis for clarification  user=%s", user_id)

    try:
        questions = await asyncio.to_thread(_run_brief_get_questions, description)
    except Exception as exc:
        logger.warning("[bot] brief analysis failed: %s", exc)
        questions = ""

    if not questions:
        CLARIFIED_DESCRIPTION[user_id] = description
        await status_msg.edit_text(
            "Описание достаточно полное, вопросов нет. Можно запускать!",
            reply_markup=start_project_keyboard(),
        )
        return

    AWAITING_CLARIFICATION.add(user_id)
    logger.info("[bot] clarification questions sent  user=%s", user_id)
    await status_msg.edit_text(
        "AI проанализировал описание и нашёл пробелы:\n\n"
        f"{questions}\n\n"
        "Ответьте одним сообщением — что знаете, в любом порядке. Я добавлю ответы к описанию.",
    )


@router.callback_query(F.data == "project:run_original")
async def run_original_callback(callback: CallbackQuery) -> None:
    AWAITING_CLARIFICATION.discard(callback.from_user.id)
    await run_project_callback(callback)


@router.callback_query(F.data == "project:run")
async def run_project_callback(callback: CallbackQuery) -> None:
    description = LAST_DESCRIPTION.get(callback.from_user.id)
    if not description:
        await _safe_callback_answer(callback, "Сначала пришлите описание бизнеса.", show_alert=True)
        return

    settings = get_settings(callback.from_user.id)
    await _safe_callback_answer(callback, "Проверяю вводные...")

    if CLARIFIED_DESCRIPTION.get(callback.from_user.id) != description:
        status_msg = await callback.message.answer("🔍 Проверяю вводные перед запуском...")
        logger.info("[bot] preflight brief analysis  user=%s", callback.from_user.id)
        try:
            questions = await asyncio.to_thread(_run_brief_get_questions, description, 10)
        except Exception as exc:
            logger.warning("[bot] preflight brief analysis failed: %s", exc)
            questions = ""

        if questions:
            AWAITING_CLARIFICATION.add(callback.from_user.id)
            await status_msg.edit_text(
                "Перед запуском нужно уточнить вводные, чтобы не получить пустой результат.\n\n"
                f"{questions}\n\n"
                "Ответьте одним сообщением — что знаете, в любом порядке. После этого запустим генерацию.",
            )
            return

        CLARIFIED_DESCRIPTION[callback.from_user.id] = description

    run_id = await _create_pipeline_run_from_callback(callback, description, settings)
    logger.info(
        "[bot] pipeline run created  user=%s  run=%s  mode=%s",
        callback.from_user.id,
        run_id,
        settings.quality_mode,
    )

    # Send live progress message and grab its ID so the worker can edit it
    loading_msg = await callback.message.answer(initial_loading_text())
    message_id = loading_msg.message_id

    run_pipeline_task.delay(run_id, callback.message.chat.id, message_id)
    logger.info("[bot] task queued  run=%s  chat=%s  msg=%s", run_id, callback.message.chat.id, message_id)
    _clear_user_project_state(callback.from_user.id)


@router.callback_query(F.data == "content:noop")
async def content_noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("content:select:"))
async def content_select_callback(callback: CallbackQuery) -> None:
    import uuid as uuid_mod
    parts = callback.data.split(":")
    run_id, page = parts[2], int(parts[3])

    async with async_session_factory() as session:
        stmt = select(FinalContentPackRow).where(
            FinalContentPackRow.pipeline_run_id == uuid_mod.UUID(run_id)
        )
        pack_row = await session.scalar(stmt)

    if pack_row is None or not pack_row.approved_content:
        await callback.answer("Данные не найдены", show_alert=True)
        return

    approved = pack_row.approved_content
    content = approved[min(page, len(approved) - 1)]
    title = content.get("title") or "Сценарий"

    logger.info("[bot] script selected  user=%s  run=%s  page=%d  title=%s",
                callback.from_user.id, run_id, page, title)
    await callback.message.answer(
        f"✅ Выбран: {title}\n\n"
        "Теперь вы можете доработать его точечно — нажмите «Уточнить доработку» "
        "и опишите что именно изменить (хук, сцена, CTA, тон и т.д.).",
        reply_markup=selected_script_keyboard(run_id, page),
    )
    await callback.answer("Сценарий выбран")


@router.callback_query(F.data.startswith("content:refine:"))
async def content_refine_callback(callback: CallbackQuery) -> None:
    import uuid as uuid_mod
    parts = callback.data.split(":")
    run_id, page = parts[2], int(parts[3])

    async with async_session_factory() as session:
        stmt = select(FinalContentPackRow).where(
            FinalContentPackRow.pipeline_run_id == uuid_mod.UUID(run_id)
        )
        pack_row = await session.scalar(stmt)

    if pack_row is None or not pack_row.approved_content:
        await callback.answer("Данные не найдены", show_alert=True)
        return

    approved = pack_row.approved_content
    content = approved[min(page, len(approved) - 1)]
    AWAITING_REFINEMENT[callback.from_user.id] = (run_id, page, content)

    logger.info("[bot] refinement requested  user=%s  run=%s  page=%d", callback.from_user.id, run_id, page)
    await callback.message.answer(
        "✍️ Что именно доработать?\n\n"
        "Опишите конкретно: хук, сцена, CTA, тон, длина и т.д.\n\n"
        "Пример: «Сделай хук провокационнее и убери упоминание цены в 3-й сцене»"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:nav:"))
async def content_nav_callback(callback: CallbackQuery) -> None:
    import uuid as uuid_mod
    parts = callback.data.split(":")
    run_id = parts[2]
    page = int(parts[3])

    async with async_session_factory() as session:
        stmt = select(FinalContentPackRow).where(
            FinalContentPackRow.pipeline_run_id == uuid_mod.UUID(run_id)
        )
        pack_row = await session.scalar(stmt)

    if pack_row is None or not pack_row.approved_content:
        await callback.answer("Результаты не найдены", show_alert=True)
        return

    approved = pack_row.approved_content
    total = len(approved)
    page = max(0, min(page, total - 1))

    text = format_content_page(approved[page], page, total)
    keyboard = content_nav_keyboard(run_id, page, total)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()
    logger.debug("[bot] content nav  user=%s  run=%s  page=%d/%d", callback.from_user.id, run_id, page + 1, total)


@router.callback_query(F.data.startswith("run:status:"))
async def run_status_callback(callback: CallbackQuery) -> None:
    run_id = callback.data.rsplit(":", 1)[-1]
    logger.debug("[bot] status check  user=%s  run=%s", callback.from_user.id, run_id)
    await callback.message.answer(
        await get_run_status_text(run_id),
        reply_markup=run_status_keyboard(run_id),
    )
    await callback.answer()


@router.message()
async def accept_company_description(message: Message) -> None:
    text = (message.text or "").strip()
    user_id = message.from_user.id
    settings = get_settings(user_id)

    # Script refinement flow
    if user_id in AWAITING_REFINEMENT:
        run_id, page, content = AWAITING_REFINEMENT.pop(user_id)
        logger.info("[bot] refinement feedback received  user=%s  len=%d", user_id, len(text))
        status_msg = await message.answer("✍️ Дорабатываю сценарий...")

        try:
            refined = await asyncio.to_thread(
                _run_script_refiner, content.get("script", {}), text, {}, {}
            )
            refined_content = {**content, "script": refined, "title": content.get("title", "") + " (доработан)"}
            page_text = format_content_page(refined_content, page, 1)
            await status_msg.edit_text(
                "✅ Доработан:\n\n" + page_text,
                reply_markup=refined_script_keyboard(run_id, page),
            )
            logger.info("[bot] refinement done  user=%s", user_id)
        except Exception as exc:
            logger.error("[bot] refinement failed  user=%s: %s", user_id, exc)
            await status_msg.edit_text(
                "❌ Не удалось доработать сценарий. Попробуйте ещё раз.",
                reply_markup=refined_script_keyboard(run_id, page),
            )
        return

    # Clarification answers flow
    if user_id in AWAITING_CLARIFICATION:
        AWAITING_CLARIFICATION.discard(user_id)
        base = LAST_DESCRIPTION.get(user_id, "")
        enriched = f"{base}\n\n--- Уточнения от пользователя ---\n{text}"
        normalized = normalize_pipeline_input(
            raw_text=enriched,
            platform=settings.platform,
            quality_mode=settings.quality_mode,
            ideas_count=settings.ideas_count,
            scripts_count=settings.scripts_count,
            telegram_user_id=user_id,
            telegram_username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code,
            telegram_chat_id=message.chat.id,
            telegram_message_id=message.message_id,
        )
        LAST_DESCRIPTION[user_id] = normalized.normalized_text
        CLARIFIED_DESCRIPTION[user_id] = normalized.normalized_text
        logger.info("[bot] clarification received  user=%s  added_len=%d  total_len=%d",
                    user_id, len(text), len(normalized.normalized_text))
        await message.answer(
            "Уточнения добавлены к описанию. Теперь у меня больше данных для анализа.\n\n"
            "Запускаем?",
            reply_markup=clarification_ready_keyboard(),
        )
        return

    normalized = normalize_pipeline_input(
        raw_text=text,
        platform=settings.platform,
        quality_mode=settings.quality_mode,
        ideas_count=settings.ideas_count,
        scripts_count=settings.scripts_count,
        telegram_user_id=user_id,
        telegram_username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
        telegram_chat_id=message.chat.id,
        telegram_message_id=message.message_id,
    )
    logger.info(
        "[bot] incoming normalized  user=%s  raw_len=%d  normalized_len=%d  too_short=%s",
        user_id,
        len(text),
        len(normalized.normalized_text),
        normalized.diagnostics.get("is_too_short"),
    )

    if len(normalized.normalized_text) < MIN_DESCRIPTION_CHARS:
        logger.debug("[bot] description too short  user=%s  len=%d", user_id, len(normalized.normalized_text))
        await message.answer(
            "Мне нужно чуть больше контекста, чтобы не генерировать пустые идеи.\n\n"
            "Напишите хотя бы: ниша, продукт, аудитория и цель продвижения.",
            reply_markup=main_menu_keyboard(),
        )
        return

    LAST_DESCRIPTION[user_id] = normalized.normalized_text
    CLARIFIED_DESCRIPTION.pop(user_id, None)
    logger.info("[bot] description accepted  user=%s  len=%d", user_id, len(normalized.normalized_text))
    await message.answer(
        accepted_description_text(settings),
        reply_markup=start_project_keyboard(),
    )


async def _create_pipeline_run_from_callback(
    callback: CallbackQuery,
    description: str,
    settings: BotUserSettings,
) -> str:
    user = callback.from_user
    normalized = normalize_pipeline_input(
        raw_text=description,
        platform=settings.platform,
        quality_mode=settings.quality_mode,
        ideas_count=settings.ideas_count,
        scripts_count=settings.scripts_count,
        telegram_user_id=user.id,
        telegram_username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
        telegram_chat_id=callback.message.chat.id,
        telegram_message_id=callback.message.message_id,
    )
    title = _project_title(normalized.normalized_text)
    async with async_session_factory() as session:
        db_user = await UserRepository(session).upsert_telegram_user(
            telegram_user_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
        )
        project = await ProjectRepository(session).create_project(
            user_id=db_user.id,
            title=title,
            project_type="telegram_smm",
        )
        project_input = await ProjectInputRepository(session).create_input(
            project_id=project.id,
            raw_text=normalized.normalized_text,
            platform=normalized.platform,
            content_goal=normalized.content_goal,
            ideas_count=normalized.ideas_count,
            scripts_count=normalized.scripts_count,
            metadata={
                "telegram_chat_id": callback.message.chat.id,
                "telegram_user_id": user.id,
                "telegram_username": user.username,
                "quality_mode": settings.quality_mode,
                "source": "telegram_bot",
                "normalized_input": normalized.model_dump(),
            },
        )
        run = await PipelineRunRepository(session).create_run(
            project_id=project.id,
            project_input_id=project_input.id,
            quality_mode=settings.quality_mode,
        )
        await session.commit()
        return str(run.id)


def _project_title(description: str) -> str:
    title = " ".join(description.split())
    if len(title) <= 64:
        return title
    return f"{title[:61].rstrip()}..."
