"""Command handlers for content bot."""

import asyncio
import logging
from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from content_bot.bot.formatters import format_process_report, send_report
from content_bot.bot.handlers.text import store_bot_post
from content_bot.bot.keyboards import seed_triage_keyboard
from content_bot.config import get_settings
from content_bot.locks import vault_lock
from content_bot.services.channel_reader import ChannelReader
from content_bot.services.git import VaultGit
from content_bot.services.processor import ContentProcessor

router = Router(name="commands")
logger = logging.getLogger(__name__)


def _get_processor() -> ContentProcessor:
    settings = get_settings()
    return ContentProcessor(
        settings.vault_path,
        settings.anthropic_api_key,
        author_name=settings.author_name,
        channel=settings.telegram_channel,
    )


def _get_git() -> VaultGit:
    settings = get_settings()
    return VaultGit(settings.vault_path)


@router.message(Command("content"))
async def cmd_content(message: Message) -> None:
    """Generate content seeds from weekly material."""
    logger.info("Content seeds triggered by user %s", message.from_user.id if message.from_user else "?")
    status_msg = await message.answer("Generating content seeds...")

    processor = _get_processor()
    git = _get_git()

    async def run_with_progress() -> dict:
        task = asyncio.create_task(
            asyncio.to_thread(processor.generate_content_seeds)
        )
        elapsed = 0
        while not task.done():
            await asyncio.sleep(30)
            elapsed += 30
            if not task.done():
                try:
                    await status_msg.edit_text(f"Generating seeds... ({elapsed // 60}m {elapsed % 60}s)")
                except Exception:
                    pass
        return await task

    async with vault_lock:
        report = await run_with_progress()

        if "error" not in report:
            today = date.today().isoformat()
            await asyncio.to_thread(git.commit_and_push, f"chore: content seeds {today}")

    formatted = format_process_report(report)
    await send_report(message, formatted, status_msg=status_msg)

    # Send triage cards for each seed
    if "error" not in report:
        processor2 = _get_processor()
        seeds = processor2._extract_seed_titles()
        # Get only seeds from current week
        today_week = f"{date.today().isocalendar()[0]}-W{date.today().isocalendar()[1]:02d}"
        current_seeds = [s for s in seeds if s["week"] == today_week]
        if current_seeds:
            await message.answer("<b>Отсортируй seeds:</b> ✅ = берём, ❌ = не берём")
            for s in current_seeds:
                try:
                    await message.answer(
                        f"<b>#{s['num']}:</b> {s['title']}",
                        reply_markup=seed_triage_keyboard(s["week"], s["num"]),
                    )
                except Exception:
                    await message.answer(
                        f"#{s['num']}: {s['title']}",
                        parse_mode=None,
                        reply_markup=seed_triage_keyboard(s["week"], s["num"]),
                    )


@router.message(Command("plan"))
async def cmd_plan(message: Message) -> None:
    """Generate weekly content plan."""
    logger.info("Content plan triggered by user %s", message.from_user.id if message.from_user else "?")
    status_msg = await message.answer("Generating content plan...")

    settings = get_settings()
    processor = _get_processor()
    git = _get_git()

    # Read channel posts for context
    channel_posts_text = ""
    if settings.telegram_channel:
        try:
            await status_msg.edit_text("Reading channel posts...")
            reader = ChannelReader(
                channel=settings.telegram_channel,
                vault_path=settings.vault_path,
            )
            posts = await reader.get_recent_posts(limit=20)
            channel_posts_text = reader.format_for_prompt(posts, limit=15)
        except Exception as e:
            logger.warning("Failed to read channel: %s", e)

    try:
        await status_msg.edit_text("Generating plan... (may take up to 3 min)")
    except Exception:
        pass

    async def run_with_progress() -> dict:
        task = asyncio.create_task(
            asyncio.to_thread(processor.generate_content_plan, channel_posts=channel_posts_text)
        )
        elapsed = 0
        while not task.done():
            await asyncio.sleep(30)
            elapsed += 30
            if not task.done():
                try:
                    await status_msg.edit_text(f"Generating plan... ({elapsed // 60}m {elapsed % 60}s)")
                except Exception:
                    pass
        return await task

    async with vault_lock:
        report = await run_with_progress()

        if "error" not in report:
            today = date.today().isoformat()
            await asyncio.to_thread(git.commit_and_push, f"chore: content plan {today}")

    formatted = format_process_report(report)
    await send_report(message, formatted, status_msg=status_msg)


@router.message(Command("seeds"))
async def cmd_seeds(message: Message) -> None:
    """Show unpublished seeds."""
    settings = get_settings()
    processor = _get_processor()

    # Get channel posts for matching
    channel_posts_text = ""
    if settings.telegram_channel:
        try:
            reader = ChannelReader(
                channel=settings.telegram_channel,
                vault_path=settings.vault_path,
            )
            posts = await reader.get_recent_posts(limit=20)
            channel_posts_text = reader.format_for_prompt(posts, limit=15)
        except Exception as e:
            logger.warning("Failed to read channel: %s", e)

    result = await asyncio.to_thread(
        processor.list_unpublished_seeds, channel_posts_text
    )

    if "error" in result:
        await message.answer(result["error"])
        return

    seeds = result["seeds"]
    total = result["total"]
    active = result["active_count"]

    text = f"<b>Content Seeds</b> ({active} active / {total} total)\n\n"
    for s in seeds[:10]:
        text += f"<b>W{s['week'][-2:]} #{s['num']}:</b> {s['title']}\n"

    if len(seeds) > 10:
        text += f"\n... и ещё {len(seeds) - 10}"

    await send_report(message, text)


@router.message(Command("note"))
async def cmd_note(message: Message) -> None:
    """Save a strategy note. Usage: /note mentoring is paused."""
    text = message.text or ""
    note_text = text.replace("/note", "", 1).strip()

    if not note_text:
        await message.answer(
            "Напиши заметку после /note. Например:\n"
            "/note менторство на паузе\n"
            "/note больше постов про AI в июне"
        )
        return

    processor = _get_processor()
    processor.save_strategy_note(note_text)
    git = _get_git()
    async with vault_lock:
        await asyncio.to_thread(git.commit_and_push, "chore: strategy note")

    await message.answer("Заметка сохранена. Буду учитывать при генерации seeds и планов.")


@router.message(Command("write"))
async def cmd_write(message: Message) -> None:
    """Write a post. Usage: /write topic or seed reference."""
    text = message.text or ""
    # Remove /write prefix
    request = text.replace("/write", "", 1).strip()

    if not request:
        await message.answer("Напиши тему после /write. Например:\n/write seed #3\n/write пост про автоматизацию")
        return

    status_msg = await message.answer("Writing post...")
    processor = _get_processor()

    report = await asyncio.to_thread(processor.write_post, request)

    formatted = format_process_report(report)
    await send_report(message, formatted, status_msg=status_msg, store=store_bot_post)
