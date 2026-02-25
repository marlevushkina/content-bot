"""Button handlers for reply keyboard."""

from aiogram import F, Router
from aiogram.types import Message

from content_bot.bot.inline_keyboards import content_menu_keyboard, plan_menu_keyboard

router = Router(name="buttons")


@router.message(F.text == "🌱 Content")
async def btn_content(message: Message) -> None:
    """Handle Content button - show inline sub-menu."""
    await message.answer(
        "🌱 <b>Content</b> - choose action:",
        reply_markup=content_menu_keyboard(),
    )


@router.message(F.text == "📋 Plan")
async def btn_plan(message: Message) -> None:
    """Handle Plan button - show inline sub-menu."""
    await message.answer(
        "📋 <b>Content plan</b> - choose action:",
        reply_markup=plan_menu_keyboard(),
    )


@router.message(F.text == "📊 Status")
async def btn_status(message: Message) -> None:
    """Handle Status button."""
    from content_bot.bot.handlers.commands import cmd_status
    await cmd_status(message)


@router.message(F.text == "❓ Help")
async def btn_help(message: Message) -> None:
    """Handle Help button."""
    from content_bot.bot.handlers.commands import cmd_help
    await cmd_help(message)
