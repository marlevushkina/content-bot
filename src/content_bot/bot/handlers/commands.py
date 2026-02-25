"""Command handlers for /start, /help, /status."""

from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from content_bot.bot.keyboards import get_main_keyboard
from content_bot.config import get_settings
from content_bot.services.storage import VaultStorage

router = Router(name="commands")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(
        "<b>Content Bot</b> - extract content ideas from your meetings\n\n"
        "Send me:\n"
        "🎤 Voice messages - I'll transcribe and save\n"
        "💬 Text - I'll save as notes\n\n"
        "<b>Commands:</b>\n"
        "/content - generate content seeds from last 7 days\n"
        "/plan - create weekly content plan\n"
        "/status - today's stats\n"
        "/help - help",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(
        "<b>How to use Content Bot:</b>\n\n"
        "1. Send voice messages — I'll transcribe and save them\n"
        "2. Send text — I'll save as daily notes\n"
        "3. Meeting transcripts from Fireflies sync automatically\n\n"
        "Then use:\n"
        "/content - AI extracts content ideas (seeds) from your material\n"
        "/plan - AI creates a weekly content plan from seeds\n\n"
        "<b>Setup:</b>\n"
        "Configure your content strategy in vault/.claude/skills/content-seeds/\n"
        "- SKILL.md - main instructions for seed generation\n"
        "- references/tone-of-voice.md - your writing style\n"
        "- references/strategy.md - content strategy\n"
        "- references/icp.md - target audience"
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    """Handle /status command."""
    settings = get_settings()
    storage = VaultStorage(settings.vault_path)

    today = date.today()
    content = storage.read_daily(today)

    if not content:
        await message.answer(f"📅 <b>{today}</b>\n\nNo entries yet.")
        return

    lines = content.strip().split("\n")
    entries = [line for line in lines if line.startswith("## ")]

    voice_count = sum(1 for e in entries if "[voice]" in e)
    text_count = sum(1 for e in entries if "[text]" in e)

    await message.answer(
        f"📅 <b>{today}</b>\n\n"
        f"Total entries: <b>{len(entries)}</b>\n"
        f"- 🎤 Voice: {voice_count}\n"
        f"- 💬 Text: {text_count}"
    )
