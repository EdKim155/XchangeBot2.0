from aiogram.fsm.state import State, StatesGroup


class CalculatorStates(StatesGroup):
    """States for the calculator feature."""
    # Add transaction states
    waiting_for_amount = State()
    waiting_for_method = State()
    waiting_for_commission = State()
    waiting_for_rate_choice = State()
    waiting_for_rate = State()
    waiting_for_confirmation = State()
    
    # Edit transaction states
    edit_amount = State()
    edit_method = State()
    edit_commission = State()
    edit_rate_choice = State()
    edit_rate = State()
    edit_confirmation = State()
