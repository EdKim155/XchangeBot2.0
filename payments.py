from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    """States for the payments feature."""
    # Pay single transaction
    waiting_for_hash = State()
    
    # Pay multiple transactions
    selecting_multiple = State()
    hash_input_type = State()
    waiting_for_common_hash = State()
    waiting_for_individual_hashes = State()
    processing_individual_hash = State()
