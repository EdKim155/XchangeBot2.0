from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Get the main menu keyboard.
    
    Returns:
        InlineKeyboardMarkup: Main menu keyboard
    """
    # В aiogram 3.x мы создаем кнопки по-другому
    buttons = [
        [
            InlineKeyboardButton(text="📊 Калькулятор", callback_data="calculator"),
            InlineKeyboardButton(text="💵 Выплаты", callback_data="payments")
        ],
        [
            InlineKeyboardButton(text="💱 Курс", callback_data="rate"),
            InlineKeyboardButton(text="📈 Статистика", callback_data="stats")
        ],
        [
            InlineKeyboardButton(text="📅 Открыть день", callback_data="open_day"),
            InlineKeyboardButton(text="❌ Закрыть день", callback_data="close_day")
        ]
    ]
    
    # Создаем клавиатуру с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    return keyboard
