"""Reply keyboards for Telegram bot."""

from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard with content commands."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🌱 Content")
    builder.button(text="📋 Plan")
    builder.button(text="📊 Status")
    builder.button(text="❓ Help")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True, is_persistent=True)
