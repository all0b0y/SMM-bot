from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from smm_bot.agents.registry import MVP_GRAPH
from smm_bot.db.models import FinalContentPack as FinalContentPackRow
from smm_bot.db.session import async_session_factory
from smm_bot.repositories.pipeline_runs import PipelineRunRepository
from smm_bot.repositories.projects import ProjectInputRepository, ProjectRepository
from smm_bot.repositories.users import UserRepository
from smm_bot.services.pipeline_runner import format_content_page, get_run_status_text
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
AWAITING_CLARIFICATION: set[int] = set()
# {user_id: (run_id, page_index, script_dict)} — ждём текст для доработки
AWAITING_REFINEMENT: dict[int, tuple[str, int, dict]] = {}


QUALITY_MODES = {
    "economy": {
        "title": "Экономный",
        "description": "Быстрее и дешевле. Подходит для тестов и черновиков.",
        "models": [
            "Brief: Qwen Flash",
            "Analysis: DeepSeek",
            "Strategy: DeepSeek",
            "Ideas: DeepSeek",
            "Critics: Qwen Flash",
            "Scripts: DeepSeek",
        ],
    },
    "balanced": {
        "title": "Баланс",
        "description": "Основной режим MVP: хорошее качество без лишней стоимости.",
        "models": [
            "Brief: Qwen Flash",
            "Audience: DeepSeek",
            "Pain/Trigger: Qwen",
            "Strategy: Qwen",
            "Ideas: DeepSeek",
            "Critics: Nvidia Nemotron",
            "Scripts: Qwen",
            "Final: Qwen Flash",
        ],
    },
    "high_quality": {
        "title": "Высокое качество",
        "description": "Для сложных ниш и важных клиентов. Медленнее, но глубже.",
        "models": [
            "Brief: Nvidia Nemotron",
            "Audience: Qwen",
            "Pain/Trigger: Qwen",
            "Strategy: Nvidia Nemotron / Qwen",
            "Ideas: DeepSeek + Qwen",
            "Critics: Nvidia Nemotron",
            "Scripts: Qwen",
            "Escalation: Qwen Plus",
        ],
    },
}


def get_settings(user_id: int) -> BotUserSettings:
    return USER_SETTINGS.setdefault(user_id, BotUserSettings())


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Старт проекта", callback_data="menu:start"),
                InlineKeyboardButton(text="📋 Что нужно", callback_data="menu:requirements"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"),
                InlineKeyboardButton(text="🤖 Модели", callback_data="menu:models"),
            ],
        ]
    )


def settings_keyboard(selected_mode: str) -> InlineKeyboardMarkup:
    def mode_button(mode: str) -> InlineKeyboardButton:
        prefix = "✅ " if mode == selected_mode else ""
        return InlineKeyboardButton(
            text=f"{prefix}{QUALITY_MODES[mode]['title']}",
            callback_data=f"settings:mode:{mode}",
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [mode_button("economy"), mode_button("balanced")],
            [mode_button("high_quality")],
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


def _run_brief_get_questions(description: str) -> str:
    """Sync: run brief agent and return formatted questions from missing_data."""
    from smm_bot.agents.llm import OpenRouterLLMClient
    from smm_bot.agents.prompts import render_prompt
    from smm_bot.agents.registry import MVP_AGENT_REGISTRY
    from smm_bot.agents.schemas import BriefOutput
    from smm_bot.core.config import get_settings as get_app_settings

    cfg = get_app_settings()
    llm = OpenRouterLLMClient(api_key=cfg.open_router_key, raise_on_failure=False)
    agent = MVP_AGENT_REGISTRY["brief"]
    prompt = render_prompt("brief", {"company_description": description})
    brief = llm.complete(agent=agent, user_prompt=prompt, output_schema=BriefOutput)

    questions: list[str] = []
    for item in brief.missing_data[:5]:
        questions.append(f"{len(questions) + 1}. {item}")
    for assumption in brief.assumptions:
        if assumption.confidence == "low" and len(questions) < 5:
            questions.append(f"{len(questions) + 1}. Уточни: {assumption.assumption}?")
    return "\n".join(questions)


def clarification_ready_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Запустить с уточнениями", callback_data="project:run")],
            [InlineKeyboardButton(text="↩️ Запустить без уточнений", callback_data="project:run_original")],
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
    mode = QUALITY_MODES[settings.quality_mode]
    return (
        "Настройки бота\n\n"
        f"Режим качества: {mode['title']}\n"
        f"Описание: {mode['description']}\n"
        f"Площадка: {settings.platform}\n"
        f"Идей: {settings.ideas_count}\n"
        f"Сценариев: {settings.scripts_count}\n\n"
        "Выберите режим качества ниже."
    )


def models_text(settings: BotUserSettings) -> str:
    lines = ["Модельная политика по режимам:\n"]
    for mode_key, mode in QUALITY_MODES.items():
        selected = " ← выбран" if mode_key == settings.quality_mode else ""
        lines.append(f"{mode['title']}{selected}")
        lines.append(mode["description"])
        lines.extend(f"• {model}" for model in mode["models"])
        lines.append("")
    return "\n".join(lines).strip()


def accepted_description_text(settings: BotUserSettings) -> str:
    mode = QUALITY_MODES[settings.quality_mode]
    total_ideas = settings.ideas_count * 3
    return (
        "Отлично, вводные приняты.\n\n"
        "Я вижу базу для SMM-разбора. Перед запуском можно изменить настройки или сразу "
        "нажать кнопку генерации.\n\n"
        f"Текущий режим: {mode['title']}\n"
        f"Площадка: {settings.platform}\n"
        f"Идей (3 генератора × {settings.ideas_count}): ~{total_ideas}\n"
        f"Финальных сценариев: {settings.scripts_count} лучших"
    )


def initial_loading_text(mode_title: str) -> str:
    bar = "░" * 16
    return (
        f"⚙️ Генерирую контент-пак\n\n"
        f"Режим: {mode_title}\n\n"
        f"[{bar}] 0/{TOTAL_AGENTS}\n\n"
        f"🚀 Запускаю агентов...\n"
        f"   Разогреваю нейроны, подождите...\n\n"
        f"⏱ 0:00"
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    logger.info("[bot] /start  user=%s", message.from_user.id)
    await message.answer(welcome_text(), reply_markup=main_menu_keyboard())


@router.message(Command("menu"))
async def menu_command(message: Message) -> None:
    logger.info("[bot] /menu  user=%s", message.from_user.id)
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    logger.info("[bot] /help  user=%s", message.from_user.id)
    await message.answer(requirements_text(), reply_markup=main_menu_keyboard())


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
    mode = callback.data.rsplit(":", 1)[-1]
    if mode not in QUALITY_MODES:
        await callback.answer("Неизвестный режим", show_alert=True)
        return

    settings = get_settings(callback.from_user.id)
    settings.quality_mode = mode
    logger.info("[bot] mode changed  user=%s  mode=%s", callback.from_user.id, mode)
    await callback.message.answer(
        f"Готово. Режим качества: {QUALITY_MODES[mode]['title']}",
        reply_markup=settings_keyboard(mode),
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
        await callback.answer("Сначала пришлите описание бизнеса.", show_alert=True)
        return

    settings = get_settings(callback.from_user.id)
    mode = QUALITY_MODES[settings.quality_mode]

    run_id = await _create_pipeline_run_from_callback(callback, description, settings)
    logger.info(
        "[bot] pipeline run created  user=%s  run=%s  mode=%s",
        callback.from_user.id,
        run_id,
        settings.quality_mode,
    )

    # Send live progress message and grab its ID so the worker can edit it
    loading_msg = await callback.message.answer(initial_loading_text(mode["title"]))
    message_id = loading_msg.message_id

    run_pipeline_task.delay(run_id, callback.message.chat.id, message_id)
    logger.info("[bot] task queued  run=%s  chat=%s  msg=%s", run_id, callback.message.chat.id, message_id)

    await callback.answer("Запуск создан")


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
        LAST_DESCRIPTION[user_id] = enriched
        logger.info("[bot] clarification received  user=%s  added_len=%d  total_len=%d",
                    user_id, len(text), len(enriched))
        await message.answer(
            "Уточнения добавлены к описанию. Теперь у меня больше данных для анализа.\n\n"
            "Запускаем?",
            reply_markup=clarification_ready_keyboard(),
        )
        return

    if len(text) < 30:
        logger.debug("[bot] description too short  user=%s  len=%d", user_id, len(text))
        await message.answer(
            "Мне нужно чуть больше контекста, чтобы не генерировать пустые идеи.\n\n"
            "Напишите хотя бы: ниша, продукт, аудитория и цель продвижения.",
            reply_markup=main_menu_keyboard(),
        )
        return

    LAST_DESCRIPTION[user_id] = text
    logger.info("[bot] description accepted  user=%s  len=%d", user_id, len(text))
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
    title = _project_title(description)
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
            raw_text=description,
            platform=settings.platform,
            ideas_count=settings.ideas_count,
            scripts_count=settings.scripts_count,
            metadata={
                "telegram_chat_id": callback.message.chat.id,
                "telegram_user_id": user.id,
                "quality_mode": settings.quality_mode,
                "source": "telegram_bot",
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
