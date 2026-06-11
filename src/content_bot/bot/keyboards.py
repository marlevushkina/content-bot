"""Reply and inline keyboards for content bot."""

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🌱 Seeds")
    builder.button(text="📋 План")
    builder.button(text="✍️ Написать")
    builder.button(text="📌 Заметка")
    builder.adjust(4)
    return builder.as_markup(resize_keyboard=True)


def content_menu_keyboard() -> InlineKeyboardMarkup:
    """Inline menu for content seeds."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои seeds", callback_data="content:my_seeds")
    builder.button(text="🔄 Новые seeds", callback_data="content:new_seeds")
    builder.adjust(1)
    return builder.as_markup()


def voice_action_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for voice message actions."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💡 Сохранить идею", callback_data="voice:save_idea")
    builder.button(text="✍️ Написать пост", callback_data="voice:write_post")
    builder.button(text="❌ Отмена", callback_data="voice:discard")
    builder.adjust(2, 1)
    return builder.as_markup()


def seed_action_keyboard(week: str, num: int) -> InlineKeyboardMarkup:
    """Inline keyboard for seed actions (single seed detail view)."""
    builder = InlineKeyboardBuilder()
    seed_id = f"{week}:{num}"
    builder.button(text="✍️ Написать пост", callback_data=f"seed:write:{seed_id}")
    builder.button(text="❌ Не берём", callback_data=f"seed:dismiss:{seed_id}")
    builder.button(text="✅ Опубликован", callback_data=f"seed:publish:{seed_id}")
    builder.adjust(1)
    return builder.as_markup()


def seed_triage_keyboard(week: str, num: int) -> InlineKeyboardMarkup:
    """Compact inline keyboard for seed triage: keep or skip."""
    builder = InlineKeyboardBuilder()
    seed_id = f"{week}:{num}"
    builder.button(text="✅", callback_data=f"triage:keep:{seed_id}")
    builder.button(text="❌", callback_data=f"triage:skip:{seed_id}")
    builder.adjust(2)
    return builder.as_markup()


def free_text_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for free text — what to do with it."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Написать пост", callback_data="freetext:write")
    builder.button(text="💡 Сохранить идею", callback_data="freetext:idea")
    builder.button(text="📌 Заметка к стратегии", callback_data="freetext:note")
    builder.adjust(1)
    return builder.as_markup()


def plan_menu_keyboard() -> InlineKeyboardMarkup:
    """Inline menu for content plan."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👁 Текущий", callback_data="plan:current")
    builder.button(text="🔄 Новый план", callback_data="plan:new")
    builder.button(text="🔄 Сверить с каналом", callback_data="plan:reconcile")
    builder.adjust(1)
    return builder.as_markup()
