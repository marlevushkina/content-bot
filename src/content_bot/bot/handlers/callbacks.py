"""Callback query handlers for inline keyboard menus."""

import asyncio
import logging
import re
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from content_bot.bot.formatters import format_process_report, send_report
from content_bot.bot.handlers.text import pop_pending, store_bot_post
from content_bot.bot.keyboards import plan_menu_keyboard, seed_action_keyboard
from content_bot.config import get_settings
from content_bot.locks import vault_lock
from content_bot.services.channel_reader import ChannelReader
from content_bot.services.git import VaultGit
from content_bot.services.processor import ContentProcessor

router = Router(name="callbacks")
logger = logging.getLogger(__name__)


class ContentSeedsState(StatesGroup):
    waiting_for_number = State()


def _get_processor() -> ContentProcessor:
    settings = get_settings()
    return ContentProcessor(
        settings.vault_path,
        settings.anthropic_api_key,
        author_name=settings.author_name,
        channel=settings.telegram_channel,
    )


# --- Content callbacks ---


@router.callback_query(F.data == "content:my_seeds")
async def on_content_my_seeds(callback: CallbackQuery, state: FSMContext) -> None:
    """Show list of unpublished seeds."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if not msg:
        return

    status_msg = await msg.answer("Loading seeds...")

    settings = get_settings()
    processor = _get_processor()

    channel_posts_text = ""
    if settings.telegram_channel:
        try:
            reader = ChannelReader(
                channel=settings.telegram_channel,
                vault_path=settings.vault_path,
            )
            posts = await reader.get_recent_posts(limit=30)
            channel_posts_text = reader.format_for_prompt(posts, limit=20)
        except Exception as e:
            logger.warning("Failed to read channel: %s", e)

    result = await asyncio.to_thread(
        processor.list_unpublished_seeds, channel_posts_text,
    )

    if "error" in result:
        await status_msg.edit_text(result["error"])
        return

    seeds = result["seeds"]
    total = result["total"]
    active = result["active_count"]

    lines = [
        f"<b>Seeds</b> ({active} active / {total} total):",
        "",
    ]
    for i, s in enumerate(seeds[:15], 1):
        lines.append(f"{i}. [{s['week']}] #{s['num']}: {s['title']}")

    lines.append("")
    lines.append("Number to expand | 'dismiss 3,5' to hide")

    text = "\n".join(lines)

    await state.set_state(ContentSeedsState.waiting_for_number)
    await state.update_data(seeds=seeds)

    try:
        await status_msg.edit_text(text)
    except Exception:
        await status_msg.edit_text(text, parse_mode=None)


@router.message(ContentSeedsState.waiting_for_number)
async def on_seed_number(message: Message, state: FSMContext) -> None:
    """Handle seed number selection or dismiss command."""
    if not message.text:
        await state.clear()
        return

    text = message.text.strip()
    data = await state.get_data()
    seeds = data.get("seeds", [])

    # Dismiss command
    dismiss_match = re.match(r"(?:удали|убери|dismiss|убрать)\s+(.+)", text, re.IGNORECASE)
    if dismiss_match:
        numbers_str = dismiss_match.group(1)
        nums = [int(n) for n in re.findall(r"\d+", numbers_str) if 1 <= int(n) <= len(seeds)]
        if not nums:
            await message.answer(f"Enter numbers 1-{len(seeds)}")
            return

        to_dismiss = [seeds[n - 1] for n in nums]
        processor = _get_processor()
        count = processor.dismiss_seeds(to_dismiss)

        await state.clear()
        await message.answer(f"Dismissed {count} seeds.")
        return

    # Expand seed by number
    try:
        num = int(text)
    except ValueError:
        await state.clear()
        return

    if num < 1 or num > len(seeds):
        await message.answer(f"Enter number 1-{len(seeds)}")
        return

    seed = seeds[num - 1]
    await state.clear()

    processor = _get_processor()
    full_html = processor._markdown_to_html(seed["full_text"])
    header = f"<b>[{seed['week']}] Seed #{seed['num']}: {seed['title']}</b>\n\n"
    response = header + full_html

    keyboard = seed_action_keyboard(seed["week"], seed["num"])
    await send_report(message, response, keyboard_last=keyboard)


@router.callback_query(F.data == "content:new_seeds")
async def on_content_new_seeds(callback: CallbackQuery, state: FSMContext) -> None:
    """Generate new content seeds."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if not msg:
        return

    from content_bot.bot.handlers.commands import cmd_content
    await cmd_content(msg)


# --- Seed triage callbacks ---


@router.callback_query(F.data.startswith("triage:"))
async def on_seed_triage(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle seed triage: keep or skip."""
    await callback.answer()

    msg = callback.message
    if not msg or not callback.data:
        return

    parts = callback.data.split(":")
    if len(parts) < 4:
        return
    action = parts[1]
    week = parts[2]
    seed_num = int(parts[3])

    processor = _get_processor()

    original_text = msg.html_text or msg.text or ""

    if action == "skip":
        processor.dismiss_seeds([{"week": week, "num": seed_num}])
        try:
            await msg.edit_text(f"<s>{original_text}</s>")
        except Exception:
            await msg.edit_reply_markup(reply_markup=None)
    elif action == "keep":
        try:
            await msg.edit_text(f"{original_text} ✅")
        except Exception:
            await msg.edit_reply_markup(reply_markup=None)


# --- Seed action callbacks ---


@router.callback_query(F.data.startswith("seed:"))
async def on_seed_action(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle seed action buttons: write/dismiss/publish."""
    await callback.answer()

    msg = callback.message
    if not msg or not callback.data:
        return

    parts = callback.data.split(":")
    if len(parts) < 4:
        return
    action = parts[1]
    week = parts[2]
    seed_num = int(parts[3])

    processor = _get_processor()
    settings = get_settings()

    if action == "dismiss":
        count = processor.dismiss_seeds([{"week": week, "num": seed_num}])
        await msg.edit_reply_markup(reply_markup=None)
        await msg.answer(f"Seed #{seed_num} убран.")

    elif action == "publish":
        processor.mark_seed_in_file(week, seed_num, "✅")
        git = VaultGit(settings.vault_path)
        async with vault_lock:
            await asyncio.to_thread(git.commit_and_push, f"chore: mark seed #{seed_num} published")
        await msg.edit_reply_markup(reply_markup=None)
        await msg.answer(f"Seed #{seed_num} отмечен как опубликованный.")

    elif action == "write":
        await msg.edit_reply_markup(reply_markup=None)
        status_msg = await msg.answer("Пишу пост...")

        request = f"Напиши пост на основе seed #{seed_num} из недели {week}"
        report = await asyncio.to_thread(processor.write_post, request)
        formatted = format_process_report(report)
        await send_report(msg, formatted, status_msg=status_msg, store=store_bot_post)


# --- Plan callbacks ---


@router.callback_query(F.data == "plan:current")
async def on_plan_current(callback: CallbackQuery, state: FSMContext) -> None:
    """Show current week's plan."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if not msg:
        return

    processor = _get_processor()
    plan_text = processor._load_current_plan()

    if not plan_text:
        await msg.answer("No plan yet. Use /plan to generate.", reply_markup=plan_menu_keyboard())
        return

    plan_html = processor._markdown_to_html(plan_text)
    await send_report(msg, plan_html)


@router.callback_query(F.data == "plan:new")
async def on_plan_new(callback: CallbackQuery, state: FSMContext) -> None:
    """Generate new plan."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if not msg:
        return

    from content_bot.bot.handlers.commands import cmd_plan
    await cmd_plan(msg)


@router.callback_query(F.data == "plan:reconcile")
async def on_plan_reconcile(callback: CallbackQuery, state: FSMContext) -> None:
    """Reconcile plan with published channel posts."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if not msg:
        return

    status_msg = await msg.answer("Сверяю план с каналом...")

    settings = get_settings()
    processor = _get_processor()

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

    if not channel_posts_text:
        await status_msg.edit_text("Не удалось прочитать посты из канала")
        return

    async with vault_lock:
        report = await asyncio.to_thread(
            processor.reconcile_plan_with_channel, channel_posts_text,
        )

        if "error" in report:
            await status_msg.edit_text(report["error"])
            return

        # Commit reconciled plan
        git = VaultGit(settings.vault_path)
        await asyncio.to_thread(git.commit_and_push, "chore: reconcile plan with channel")

    formatted = format_process_report(report)
    await send_report(msg, formatted, status_msg=status_msg)


# --- Free text callbacks ---


@router.callback_query(F.data.startswith("freetext:"))
async def on_freetext_action(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle free text action buttons."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if not msg:
        return

    text = pop_pending(msg.message_id)
    if not text:
        await msg.edit_text("Текст не найден, попробуй ещё раз.")
        return

    action = callback.data.split(":")[1]
    settings = get_settings()
    processor = _get_processor()

    if action == "write":
        await msg.edit_text("Пишу пост...")
        await msg.chat.do(action="typing")

        report = await asyncio.to_thread(processor.write_post, text)
        formatted = format_process_report(report)
        await send_report(msg, formatted, status_msg=msg, store=store_bot_post)

    elif action == "idea":
        processor.save_content_idea(text)
        git = VaultGit(settings.vault_path)
        async with vault_lock:
            await asyncio.to_thread(git.commit_and_push, "chore: content idea")
        await msg.edit_text("Идея сохранена в content seeds.")

    elif action == "note":
        processor.save_strategy_note(text)
        git = VaultGit(settings.vault_path)
        async with vault_lock:
            await asyncio.to_thread(git.commit_and_push, "chore: strategy note")
        await msg.edit_text("Заметка сохранена. Буду учитывать при генерации seeds и планов.")
