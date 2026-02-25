"""Telegram bot initialization and polling."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from content_bot.config import Settings

logger = logging.getLogger(__name__)


def create_bot(settings: Settings) -> Bot:
    """Create and configure the Telegram bot."""
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Create and configure the dispatcher with routers."""
    from content_bot.bot.handlers import buttons, callbacks, commands, content, content_plan, text, voice

    dp = Dispatcher(storage=MemoryStorage())

    # Register routers - ORDER MATTERS
    dp.include_router(commands.router)
    dp.include_router(content.router)
    dp.include_router(content_plan.router)
    dp.include_router(callbacks.router)
    dp.include_router(buttons.router)
    dp.include_router(voice.router)
    dp.include_router(text.router)  # Must be last (catch-all for text)
    return dp


def create_auth_middleware(settings: Settings):
    """Create middleware to check user authorization."""

    async def auth_middleware(
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        if settings.allow_all_users:
            return await handler(event, data)

        user = None
        if event.message:
            user = event.message.from_user
        elif event.callback_query:
            user = event.callback_query.from_user

        if not settings.allowed_user_ids:
            logger.warning("Access denied: no allowed_user_ids configured")
            return None

        if user and user.id not in settings.allowed_user_ids:
            logger.warning("Unauthorized access attempt from user %s", user.id)
            return None

        return await handler(event, data)

    return auth_middleware


async def run_bot(settings: Settings) -> None:
    """Run the bot with polling."""
    bot = create_bot(settings)
    dp = create_dispatcher()

    dp.update.middleware(create_auth_middleware(settings))

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
