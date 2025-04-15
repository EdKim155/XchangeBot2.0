from aiogram.fsm.state import StatesGroup, State

class DayState(StatesGroup):
    """Состояния для настройки дня."""
    menu = State()         # Основное меню настройки дня
    rate = State()         # Ввод курса
    commission = State()   # Ввод комиссии
    confirm = State()      # Подтверждение настроек

class DayStates(StatesGroup):
    """Состояния для старой настройки дня (для обратной совместимости)."""
    waiting_for_rate = State()         # Ожидание ввода курса
    waiting_for_commission = State()   # Ожидание ввода комиссии
    waiting_for_confirmation = State() # Ожидание подтверждения