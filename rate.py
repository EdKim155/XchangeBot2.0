from aiogram.fsm.state import State, StatesGroup


class RateStates(StatesGroup):
    """States for the rate feature."""
    waiting_for_rate = State()
