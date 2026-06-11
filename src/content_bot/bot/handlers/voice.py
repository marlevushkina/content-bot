"""Voice message handler — transcribe and offer content actions."""

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.types import CallbackQuery, Message

from content_bot.bot.formatters import format_process_report, send_report
from content_bot.bot.keyboards import voice_action_keyboard
from content_bot.config import get_settings
from content_bot.services.processor import ContentProcessor
from content_bot.services.transcription import transcribe_voice

router = Router(name="voice")
logger = logging.getLogger(__name__)

# Temporary storage for transcripts keyed by message_id
_transcripts: dict[int, str] = {}


@router.message(lambda m: m.voice is not None)
async def handle_voice(message: Message, bot: Bot) -> None:
    """Transcribe voice message and offer actions."""
    if not message.voice or not message.from_user:
        return

    settings = get_settings()
    if not settings.deepgram_api_key:
        await message.answer("Deepgram API key not configured.")
        return

    await message.chat.do(action="typing")

    try:
        transcript = await transcribe_voice(message, bot, settings.deepgram_api_key)
        if not transcript:
            await message.answer("Не удалось распознать речь.")
            return

        reply = await message.answer(
            f"🎤 <i>{transcript}</i>",
            reply_markup=voice_action_keyboard(),
        )
        _transcripts[reply.message_id] = transcript
        logger.info("Voice transcribed: %d chars", len(transcript))

    except Exception:
        logger.exception("Error processing voice message")
        await message.answer("Не удалось обработать голосовое сообщение, попробуй ещё раз.")


@router.callback_query(lambda c: c.data and c.data.startswith("voice:"))
async def handle_voice_action(callback: CallbackQuery) -> None:
    """Handle voice action buttons."""
    if not callback.message or not callback.data:
        return

    action = callback.data.split(":")[1]
    transcript = _transcripts.pop(callback.message.message_id, None)

    if not transcript:
        await callback.answer("Текст не найден, попробуй ещё раз.")
        return

    settings = get_settings()
    processor = ContentProcessor(
        settings.vault_path,
        settings.anthropic_api_key,
        author_name=settings.author_name,
        channel=settings.telegram_channel,
    )

    if action == "save_idea":
        processor.save_content_idea(transcript)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("✅ Идея сохранена в content seeds.")
        await callback.answer()

    elif action == "write_post":
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer()
        status_msg = await callback.message.answer("Пишу пост...")

        report = await asyncio.to_thread(processor.write_post, transcript)

        if "error" in report:
            await status_msg.edit_text(f"Ошибка: {report['error']}")
            return

        formatted = format_process_report(report)
        await send_report(callback.message, formatted, status_msg=status_msg)

    elif action == "discard":
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Отменено.")
