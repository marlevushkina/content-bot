"""Callback query handlers for inline keyboard menus."""

import asyncio
import logging
import re
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from content_bot.bot.formatters import format_process_report, split_html_report
from content_bot.bot.states import ContentSeedsState
from content_bot.config import get_settings
from content_bot.services.git import VaultGit
from content_bot.services.processor import ContentProcessor

router = Router(name="callbacks")
logger = logging.getLogger(__name__)


def _get_processor() -> ContentProcessor:
    settings = get_settings()
    return ContentProcessor(settings.vault_path)


# --- Content callbacks ---


@router.callback_query(F.data == "content:my_seeds")
async def on_content_my_seeds(callback: CallbackQuery, state: FSMContext) -> None:
    """Show list of unpublished seeds."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if not msg:
        return

    status_msg = await msg.answer("⏳ Loading seeds...")

    settings = get_settings()
    processor = _get_processor()

    channel_posts_text = ""
    if settings.telegram_channel:
        try:
            from content_bot.services.channel_reader import ChannelReader

            reader = ChannelReader(
                channel=settings.telegram_channel,
                vault_path=settings.vault_path,
            )
            posts = await reader.get_recent_posts(limit=30)
            channel_posts_text = reader.format_for_prompt(posts, limit=20)
        except Exception as e:
            logger.warning("Failed to read channel for seed matching: %s", e)

    result = await asyncio.to_thread(
        processor.list_unpublished_seeds, channel_posts_text,
    )

    if "error" in result:
        await status_msg.edit_text(f"❌ {result['error']}")
        return

    unpublished = result["unpublished"]
    total = result["total"]

    if not unpublished:
        await status_msg.edit_text(
            f"All {total} seeds published! Run /content for new ones.",
        )
        return

    lines = [
        f"🌱 <b>Unpublished seeds</b> ({len(unpublished)} of {total}):",
        "",
    ]
    for i, s in enumerate(unpublished, 1):
        lines.append(f"{i}. [{s['week']}] #{s['num']}: {s['title']}")

    if result.get("dismissed_count"):
        lines.append(f"🗑 Hidden: {result['dismissed_count']}")
    lines.append("")
    lines.append("Reply with number to expand seed")

    text = "\n".join(lines)

    await state.set_state(ContentSeedsState.waiting_for_number)
    await state.update_data(seeds=unpublished)

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

    # Check for dismiss command
    dismiss_match = re.match(r"(?:dismiss|remove|hide)\s+(.+)", text, re.IGNORECASE)
    if dismiss_match:
        numbers_str = dismiss_match.group(1)
        nums = [int(n) for n in re.findall(r"\d+", numbers_str) if 1 <= int(n) <= len(seeds)]
        if not nums:
            await message.answer(f"Enter numbers from 1 to {len(seeds)}")
            return

        to_dismiss = [seeds[n - 1] for n in nums]
        processor = _get_processor()
        count = processor.dismiss_seeds(to_dismiss)

        titles = ", ".join(f"#{seeds[n - 1]['num']}" for n in nums)
        await state.clear()
        await message.answer(f"🗑 Hidden {count} seeds: {titles}")
        return

    try:
        num = int(text)
    except ValueError:
        await state.clear()
        return

    if num < 1 or num > len(seeds):
        await message.answer(f"Enter a number from 1 to {len(seeds)}")
        return

    seed = seeds[num - 1]
    await state.clear()

    processor = _get_processor()
    full_html = processor._markdown_to_html(seed["full_text"])

    header = f"🌱 <b>[{seed['week']}] Seed #{seed['num']}: {seed['title']}</b>\n\n"
    response = header + full_html

    if len(response) > 4000:
        response = response[:3950] + "\n\n<i>...(truncated)</i>"

    try:
        await message.answer(response)
    except Exception:
        await message.answer(response, parse_mode=None)


@router.callback_query(F.data == "content:new_seeds")
async def on_content_new_seeds(callback: CallbackQuery, state: FSMContext) -> None:
    """Generate new content seeds."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if not msg:
        return

    from content_bot.bot.handlers.content import cmd_content
    await cmd_content(msg)


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
    plan_data = processor.get_current_plan()

    if "error" in plan_data:
        await msg.answer(
            f"📋 {plan_data['error']}\n\nPress 'New plan' to generate.",
        )
        return

    plan_html = processor._markdown_to_html(plan_data["plan"])
    header = f"📋 <b>Content plan {plan_data['week']}</b>\n\n"
    response = header + plan_html

    parts = split_html_report(response)
    for part in parts:
        try:
            await msg.answer(part)
        except Exception:
            await msg.answer(part, parse_mode=None)


@router.callback_query(F.data == "plan:new")
async def on_plan_new(callback: CallbackQuery, state: FSMContext) -> None:
    """Generate new plan with smart week detection."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if not msg:
        return

    processor = _get_processor()

    if processor.plan_exists_for_week(0):
        target_date = date.today() + timedelta(weeks=1)
        year, week, _ = target_date.isocalendar()
        week_label = f"{year}-W{week:02d}"
        status_msg = await msg.answer(
            f"⏳ Current week has a plan. Generating for {week_label}...",
        )
    else:
        target_date = date.today()
        year, week, _ = target_date.isocalendar()
        week_label = f"{year}-W{week:02d}"
        status_msg = await msg.answer(
            f"⏳ Generating plan for {week_label}...",
        )

    settings = get_settings()
    git = VaultGit(settings.vault_path)

    channel_posts_text = ""
    if settings.telegram_channel:
        try:
            from content_bot.services.channel_reader import ChannelReader

            reader = ChannelReader(
                channel=settings.telegram_channel,
                vault_path=settings.vault_path,
            )
            posts = await reader.get_recent_posts(limit=20)
            channel_posts_text = reader.format_for_prompt(posts, limit=15)
        except Exception as e:
            logger.warning("Failed to read channel: %s", e)

    async def run_with_progress() -> dict:
        task = asyncio.create_task(
            asyncio.to_thread(
                processor.generate_content_plan,
                channel_posts=channel_posts_text,
                target_date=target_date,
            ),
        )

        elapsed = 0
        while not task.done():
            await asyncio.sleep(30)
            elapsed += 30
            if not task.done():
                try:
                    await status_msg.edit_text(
                        f"⏳ Creating plan {week_label}... "
                        f"({elapsed // 60}m {elapsed % 60}s)",
                    )
                except Exception:
                    pass

        return await task

    report = await run_with_progress()

    if "error" not in report:
        await asyncio.to_thread(
            git.commit_and_push, f"chore: content plan {week_label}",
        )

    formatted = format_process_report(report)
    parts = split_html_report(formatted)

    try:
        await status_msg.edit_text(parts[0])
    except Exception:
        await status_msg.edit_text(parts[0], parse_mode=None)

    for part in parts[1:]:
        try:
            await msg.answer(part)
        except Exception:
            await msg.answer(part, parse_mode=None)


@router.callback_query(F.data == "plan:reconcile")
async def on_plan_reconcile(callback: CallbackQuery, state: FSMContext) -> None:
    """Reconcile plan with published channel posts."""
    await callback.answer()
    await state.clear()

    msg = callback.message
    if not msg:
        return

    status_msg = await msg.answer("⏳ Reconciling plan with channel...")

    settings = get_settings()
    processor = _get_processor()
    git = VaultGit(settings.vault_path)

    channel_posts_text = ""
    if settings.telegram_channel:
        try:
            from content_bot.services.channel_reader import ChannelReader

            reader = ChannelReader(
                channel=settings.telegram_channel,
                vault_path=settings.vault_path,
            )
            posts = await reader.get_recent_posts(limit=20)
            channel_posts_text = reader.format_for_prompt(posts, limit=15)
        except Exception as e:
            logger.warning("Failed to read channel: %s", e)

    if not channel_posts_text:
        await status_msg.edit_text("❌ Could not read channel posts")
        return

    async def run_with_progress() -> dict:
        task = asyncio.create_task(
            asyncio.to_thread(
                processor.reconcile_plan_with_channel, channel_posts_text,
            ),
        )

        elapsed = 0
        while not task.done():
            await asyncio.sleep(30)
            elapsed += 30
            if not task.done():
                try:
                    await status_msg.edit_text(
                        f"⏳ Reconciling... ({elapsed // 60}m {elapsed % 60}s)",
                    )
                except Exception:
                    pass

        return await task

    report = await run_with_progress()

    if "error" not in report:
        await asyncio.to_thread(
            git.commit_and_push,
            f"chore: reconcile plan {date.today().isoformat()}",
        )

    formatted = format_process_report(report)
    parts = split_html_report(formatted)

    try:
        await status_msg.edit_text(parts[0])
    except Exception:
        await status_msg.edit_text(parts[0], parse_mode=None)

    for part in parts[1:]:
        try:
            await msg.answer(part)
        except Exception:
            await msg.answer(part, parse_mode=None)
