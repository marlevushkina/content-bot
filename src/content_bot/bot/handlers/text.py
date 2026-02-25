"""Text message handler."""

import asyncio
import logging
from datetime import date, datetime

from aiogram import Router
from aiogram.types import Message

from content_bot.bot.formatters import format_process_report, split_html_report
from content_bot.config import get_settings
from content_bot.services.git import VaultGit
from content_bot.services.processor import ContentProcessor
from content_bot.services.session import SessionStore
from content_bot.services.storage import VaultStorage

router = Router(name="text")
logger = logging.getLogger(__name__)


def _is_reply_to_bot(message: Message) -> bool:
    """Check if user is replying to a bot message."""
    if not message.reply_to_message:
        return False
    reply = message.reply_to_message
    return reply.from_user is not None and reply.from_user.is_bot


def _is_reply_to_plan(message: Message) -> bool:
    """Check if user is replying to a plan message."""
    if not _is_reply_to_bot(message):
        return False
    original = message.reply_to_message.text or ""
    plan_markers = ["Content plan", "content plan", "Seed #", "TELEGRAM:", "LINKEDIN:"]
    return any(marker in original for marker in plan_markers)


async def _handle_plan_edit(message: Message) -> None:
    """Handle reply to a plan message - edit the plan via Claude."""
    status_msg = await message.answer("⏳ Editing plan...")

    settings = get_settings()
    processor = ContentProcessor(settings.vault_path)
    git = VaultGit(settings.vault_path)

    async def run_with_progress() -> dict:
        task = asyncio.create_task(
            asyncio.to_thread(processor.edit_plan, message.text),
        )

        elapsed = 0
        while not task.done():
            await asyncio.sleep(30)
            elapsed += 30
            if not task.done():
                try:
                    await status_msg.edit_text(
                        f"⏳ Editing plan... ({elapsed // 60}m {elapsed % 60}s)",
                    )
                except Exception:
                    pass

        return await task

    report = await run_with_progress()

    if "error" not in report:
        await asyncio.to_thread(
            git.commit_and_push,
            f"chore: edit plan {date.today().isoformat()}",
        )

    formatted = format_process_report(report)
    parts = split_html_report(formatted)

    try:
        await status_msg.edit_text(parts[0])
    except Exception:
        await status_msg.edit_text(parts[0], parse_mode=None)

    for part in parts[1:]:
        try:
            await message.answer(part)
        except Exception:
            await message.answer(part, parse_mode=None)


@router.message(lambda m: m.text is not None and not m.text.startswith("/"))
async def handle_text(message: Message) -> None:
    """Handle text messages - save as daily notes or edit plan."""
    if not message.text or not message.from_user:
        return

    # If replying to a plan message — edit the plan
    if _is_reply_to_plan(message):
        logger.info("Reply to plan from user %s, editing plan", message.from_user.id)
        await _handle_plan_edit(message)
        return

    # Otherwise — save as note
    settings = get_settings()
    storage = VaultStorage(settings.vault_path)

    timestamp = datetime.fromtimestamp(message.date.timestamp())
    storage.append_to_daily(message.text, timestamp, "[text]")

    session = SessionStore(settings.vault_path)
    session.append(
        message.from_user.id,
        "text",
        text=message.text,
        msg_id=message.message_id,
    )

    await message.answer("✓ Saved")
    logger.info("Text message saved: %d chars", len(message.text))
