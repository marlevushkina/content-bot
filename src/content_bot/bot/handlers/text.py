"""Catch-all text handler — offers action choice or handles reply edits."""

import asyncio
import logging

from aiogram import Router
from aiogram.types import Message

from content_bot.bot.formatters import format_process_report, send_report
from content_bot.bot.keyboards import free_text_keyboard
from content_bot.config import get_settings
from content_bot.services.processor import ContentProcessor

router = Router(name="text")
logger = logging.getLogger(__name__)

# Temporary storage for free text keyed by message_id of bot reply
_pending_text: dict[int, str] = {}

# Store bot's generated posts keyed by message_id for edit context
_bot_posts: dict[int, str] = {}


def store_pending(reply_msg_id: int, text: str) -> None:
    """Store text for later action via callback."""
    _pending_text[reply_msg_id] = text
    if len(_pending_text) > 20:
        oldest = next(iter(_pending_text))
        _pending_text.pop(oldest, None)


def pop_pending(msg_id: int) -> str | None:
    """Retrieve and remove pending text."""
    return _pending_text.pop(msg_id, None)


def store_bot_post(msg_id: int, text: str) -> None:
    """Store bot's generated post for potential edit replies."""
    _bot_posts[msg_id] = text
    if len(_bot_posts) > 30:
        oldest = next(iter(_bot_posts))
        _bot_posts.pop(oldest, None)


def get_bot_post(msg_id: int) -> str | None:
    """Get stored bot post by message id."""
    return _bot_posts.get(msg_id)


@router.message()
async def handle_text(message: Message) -> None:
    """Handle free text — reply to bot post = edits, otherwise action menu."""
    text = message.text
    if not text:
        return

    if len(text) < 5:
        return

    # Check if this is a reply to a bot's generated post
    if message.reply_to_message and message.reply_to_message.from_user:
        bot_user = message.reply_to_message.from_user
        if bot_user.is_bot:
            original_post = get_bot_post(message.reply_to_message.message_id)
            if original_post:
                await _handle_edit_request(message, original_post, text)
                return

    reply = await message.answer(
        "Что сделать с этим текстом?",
        reply_markup=free_text_keyboard(),
    )
    store_pending(reply.message_id, text)


async def _handle_edit_request(message: Message, original_post: str, edit_request: str) -> None:
    """Apply user's edits to a previously generated post."""
    status_msg = await message.answer("Вношу правки...")

    settings = get_settings()
    processor = ContentProcessor(
        settings.vault_path,
        settings.anthropic_api_key,
        author_name=settings.author_name,
        channel=settings.telegram_channel,
    )

    report = await asyncio.to_thread(
        processor.refine_post, original_post, edit_request
    )

    formatted = format_process_report(report)
    await send_report(message, formatted, status_msg=status_msg, store=store_bot_post)
