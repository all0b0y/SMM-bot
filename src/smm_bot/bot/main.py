from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, MenuButtonCommands

from smm_bot.bot.router import router
from smm_bot.core.config import get_settings


logger = logging.getLogger(__name__)


async def run_bot() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть главное меню"),
            BotCommand(command="menu", description="Кнопки запуска и настроек"),
            BotCommand(command="settings", description="Настроить режим качества"),
            BotCommand(command="help", description="Что нужно для запуска"),
        ]
    )
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Telegram bot polling started")
    try:
        await dispatcher.start_polling(
            bot,
            polling_timeout=settings.bot_polling_timeout,
        )
    finally:
        await bot.session.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence noisy third-party loggers
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
