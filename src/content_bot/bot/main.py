"""Telegram bot initialization and polling."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, Update

from content_bot.bot.keyboards import (
    content_menu_keyboard,
    get_main_keyboard,
    plan_menu_keyboard,
)
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
    from content_bot.bot.handlers import callbacks, commands, text, voice

    dp = Dispatcher(storage=MemoryStorage())

    @dp.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        await message.answer(
            "<b>Content Bot</b>\n\n"
            "Генерация контента для Telegram-канала и LinkedIn.\n\n"
            "<b>Команды:</b>\n"
            "/content - генерация content seeds\n"
            "/plan - контент-план на неделю\n"
            "/seeds - посмотреть накопленные seeds\n"
            "/help - помощь",
            reply_markup=get_main_keyboard(),
        )

    @dp.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(
            "<b>Content Bot - команды</b>\n\n"
            "/content - сгенерировать seeds из материала за неделю\n"
            "/plan - составить контент-план (TG + LinkedIn)\n"
            "/seeds - список неопубликованных seeds\n"
            "/write - написать пост (напиши тему после команды)\n"
            "/note - заметка к стратегии (бот запомнит)\n\n"
            "Свободный текст — бот спросит, что с ним сделать.",
            reply_markup=get_main_keyboard(),
        )

    # Reply keyboard button handlers
    @dp.message(F.text == "🌱 Seeds")
    async def btn_seeds(message: Message) -> None:
        await message.answer(
            "🌱 <b>Контент</b> - выбери действие:",
            reply_markup=content_menu_keyboard(),
        )

    @dp.message(F.text == "📋 План")
    async def btn_plan(message: Message) -> None:
        await message.answer(
            "📋 <b>Контент-план</b> - выбери действие:",
            reply_markup=plan_menu_keyboard(),
        )

    @dp.message(F.text == "✍️ Написать")
    async def btn_write(message: Message) -> None:
        await message.answer(
            "✍️ Напиши тему или идею поста — я помогу оформить.",
        )

    @dp.message(F.text == "📌 Заметка")
    async def btn_note(message: Message) -> None:
        await message.answer(
            "📌 Напиши заметку — я сохраню и буду учитывать при генерации.\n\n"
            "Используй /note и текст. Например:\n"
            "<code>/note менторство на паузе</code>",
        )

    dp.include_router(voice.router)
    dp.include_router(commands.router)
    dp.include_router(callbacks.router)
    dp.include_router(text.router)

    return dp


def create_auth_middleware(settings: Settings) -> Callable:
    """Create middleware to check user authorization."""

    async def auth_middleware(
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        if not settings.allowed_user_ids:
            return await handler(event, data)

        user = None
        if event.message:
            user = event.message.from_user
        elif event.callback_query:
            user = event.callback_query.from_user

        if user and user.id not in settings.allowed_user_ids:
            logger.warning("Unauthorized access attempt from user %s", user.id)
            return None

        return await handler(event, data)

    return auth_middleware


async def run_bot(settings: Settings) -> None:
    """Run the bot with polling."""
    bot = create_bot(settings)
    dp = create_dispatcher()

    if not settings.allowed_user_ids:
        logger.warning(
            "ALLOWED_USER_IDS is empty — bot is OPEN to everyone "
            "(anyone can trigger paid API calls). Set it in .env to restrict access."
        )

    dp.update.middleware(create_auth_middleware(settings))

    logger.info("Starting content bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
