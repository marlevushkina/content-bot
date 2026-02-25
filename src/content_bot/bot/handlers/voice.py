"""Voice message handler."""

import logging
from datetime import datetime

from aiogram import Bot, Router
from aiogram.types import Message

from content_bot.config import get_settings
from content_bot.services.session import SessionStore
from content_bot.services.storage import VaultStorage
from content_bot.services.transcription import DeepgramTranscriber

router = Router(name="voice")
logger = logging.getLogger(__name__)


@router.message(lambda m: m.voice is not None)
async def handle_voice(message: Message, bot: Bot) -> None:
    """Handle voice messages - transcribe and save."""
    if not message.voice or not message.from_user:
        return

    await message.chat.do(action="typing")

    settings = get_settings()
    storage = VaultStorage(settings.vault_path)
    transcriber = DeepgramTranscriber(settings.deepgram_api_key)

    try:
        file = await bot.get_file(message.voice.file_id)
        if not file.file_path:
            await message.answer("Failed to download voice message")
            return

        file_bytes = await bot.download_file(file.file_path)
        if not file_bytes:
            await message.answer("Failed to download voice message")
            return

        audio_bytes = file_bytes.read()
        transcript = await transcriber.transcribe(audio_bytes)

        if not transcript:
            await message.answer("Could not transcribe audio")
            return

        timestamp = datetime.fromtimestamp(message.date.timestamp())
        storage.append_to_daily(transcript, timestamp, "[voice]")

        session = SessionStore(settings.vault_path)
        session.append(
            message.from_user.id,
            "voice",
            text=transcript,
            duration=message.voice.duration,
            msg_id=message.message_id,
        )

        await message.answer(f"🎤 {transcript}\n\n✓ Saved")
        logger.info("Voice message saved: %d chars", len(transcript))

    except Exception as e:
        logger.exception("Error processing voice message")
        await message.answer(f"Error: {e}")
