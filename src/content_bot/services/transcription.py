"""Voice transcription using Deepgram."""

import logging

from aiogram import Bot
from aiogram.types import Message
from deepgram import DeepgramClient

logger = logging.getLogger(__name__)


async def transcribe_voice(message: Message, bot: Bot, api_key: str) -> str | None:
    """Download voice message from Telegram and transcribe via Deepgram."""
    file = await bot.get_file(message.voice.file_id)
    if not file.file_path:
        return None

    file_bytes = await bot.download_file(file.file_path)
    if not file_bytes:
        return None

    audio_bytes = file_bytes.read()
    logger.info("Transcribing voice: %d bytes", len(audio_bytes))

    client = DeepgramClient(api_key=api_key)

    response = client.listen.v1.media.transcribe_file(
        request=audio_bytes,
        model="nova-3",
        language="ru",
        punctuate=True,
        smart_format=True,
    )

    transcript = (
        response.results.channels[0].alternatives[0].transcript
        if response.results
        and response.results.channels
        and response.results.channels[0].alternatives
        else ""
    )

    return transcript if transcript else None
