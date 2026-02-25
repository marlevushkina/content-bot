"""Bot FSM states."""

from aiogram.fsm.state import State, StatesGroup


class ContentSeedsState(StatesGroup):
    """States for viewing seeds by number."""

    waiting_for_number = State()
