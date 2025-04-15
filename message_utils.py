import logging
import datetime
from typing import Optional, Dict, Any, List, Callable, Union
from sheets import MSK_TIMEZONE  # Импортируем московское время (UTC+3)

from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from keyboards.main_menu import get_main_menu_keyboard

from sheets import sheets_client


# Dictionary to store header message IDs for each chat
header_messages = {}

# Dictionary to store temporary messages to clean up later
# Format: {chat_id: [list of message IDs]}
temp_messages = {}

# Dictionary to store bot messages for each chat (except notifications)
# Format: {chat_id: [list of message IDs]}
bot_messages = {}

# Dictionary to store input request messages that need to be cleaned up after processing
# Format: {chat_id: [list of message IDs]}
input_request_messages = {}


async def send_header(bot: Bot, chat_id: int) -> Optional[Message]:
    """
    Send the interactive header to the chat.
    
    Args:
        bot: Bot instance
        chat_id: Chat ID
        
    Returns:
        Optional[Message]: Sent message or None if failed
    """
    # Prepare the text for the header
    try:
        # Получаем данные для шапки
        today = datetime.datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
        
        # Получаем статистику из data_manager
        from data_manager import data_manager
        
        # Получаем статистику с принудительным обновлением
        stats = data_manager.get_daily_statistics(chat_id, force_refresh=True)
        logging.info(f"Получена статистика для шапки в chat_id {chat_id}: {stats}")
        
        # Проверяем наличие ключей в статистике и устанавливаем значения по умолчанию если их нет
        if not stats or "transactions_count" not in stats:
            logging.warning(f"Статистика для chat_id {chat_id} пуста или не содержит необходимых ключей")
            stats = {
                "total_amount": 0,
                "awaiting_amount": 0,
                "to_pay_amount": 0,
                "paid_amount": 0,
                "avg_rate": 0,
                "avg_commission": 0,
                "transactions_count": 0,
                "unpaid_usdt": 0,
                "to_pay_usdt": 0,
                "total_usdt": 0,
                "paid_usdt": 0,
                "methods_count": {}
            }
        
        # Получаем настройки дня
        day_settings = data_manager.get_day_settings(chat_id) or {"rate": 0, "commission_percent": 0}
        current_rate_raw = day_settings.get("rate", 0)
        commission_percent = day_settings.get("commission_percent", 0)
        
        # Обрабатываем курс - извлекаем числовое значение из разных форматов
        # Курс может быть как числом, так и строкой в формате "92.50 USDT" или "92.50₽"
        if isinstance(current_rate_raw, str):
            # Удаляем кавычки и символ рубля, если они есть
            rate_str = current_rate_raw.replace('"', '').replace('₽', '').strip()
            if "USDT" in rate_str:
                # Если уже в формате USDT, извлекаем числовое значение
                current_rate = float(rate_str.replace('USDT', '').strip())
                display_rate = f'"{current_rate:.2f} USDT"'
            else:
                # Если в другом формате, просто преобразуем в число
                current_rate = float(rate_str)
                display_rate = f'"{current_rate:.2f} USDT"'
        else:
            # Если курс числовой
            current_rate = float(current_rate_raw) if current_rate_raw else 0
            if current_rate > 0:
                display_rate = f'"{current_rate:.2f} USDT"'
            else:
                display_rate = "Не установлен"
            
        # Рассчитываем эквивалент в USDT
        # Если курс = 0, используем значение 90 как минимальное для расчетов USDT, чтобы отображать его всегда
        usdt_rate = current_rate if current_rate else 90
        
        # Получаем статистические данные
        total_amount = stats.get("total_amount", 0)
        awaiting_amount = stats.get("awaiting_amount", 0)
        paid_amount = stats.get("paid_amount", 0)
        to_pay_amount = stats.get("to_pay_amount", 0)
        
        # Получаем значения в USDT, если они есть в статистике, или рассчитываем
        unpaid_usdt = stats.get("unpaid_usdt", round(awaiting_amount / usdt_rate, 1) if usdt_rate > 0 else 0)
        to_pay_usdt = stats.get("to_pay_usdt", round(to_pay_amount / usdt_rate, 1) if usdt_rate > 0 else 0)
        total_usdt = stats.get("total_usdt", round(total_amount / usdt_rate, 1) if usdt_rate > 0 else 0)
        paid_usdt = stats.get("paid_usdt", round(paid_amount / usdt_rate, 1) if usdt_rate > 0 else 0)
        
        # Format the header
        header_text = (
            f"🌠 [OCTOFX] {today}\n\n"
            f"🆔 Айди чата: {chat_id}\n"
            f"🧮 Курс: {display_rate} | Комиссия: {commission_percent}%\n\n"
            f"⚜️ Статистика:\n\n"
            f"⏳ Ожидаем: {awaiting_amount:,.1f}₽ ({unpaid_usdt:.1f} USDT)\n"
            f"💳 К выплате: {to_pay_amount:,.1f}₽ ({to_pay_usdt:.1f} USDT)\n"
            f"💴 Общая сумма: {total_amount:,.1f}₽ ({total_usdt:.1f} USDT)\n\n"
            f"💸 Выплачено: {paid_amount:,.1f}₽ ({paid_usdt:.1f} USDT)\n\n"
            f"Выберите действие из меню ниже"
        )
        
        # Send the header
        try:
            message = await bot.send_message(
                chat_id,
                header_text,
                reply_markup=get_main_menu_keyboard()
            )
            
            # Store the message ID
            header_messages[chat_id] = message.message_id
            
            # Не регистрируем шапку как обычное сообщение бота, 
            # так как она имеет специальную обработку
            
            return message
        except TelegramBadRequest as e:
            if "business connection not found" in str(e).lower():
                logging.error(f"Невозможно отправить сообщение в бизнес-чат: {e}")
                # Мы все равно сохраняем данные в памяти, чтобы статистика обновлялась
                logging.info(f"Статистика успешно обновлена для chat_id {chat_id}")
                return None
            else:
                raise
            
    except Exception as e:
        logging.error(f"Error sending header: {e}")
        return None


async def update_header(bot: Bot, chat_id: int) -> Optional[Message]:
    """
    Update the interactive header in the chat.
    
    Args:
        bot: Bot instance
        chat_id: Chat ID
        
    Returns:
        Optional[Message]: Updated message or None if failed
    """
    # If no header exists for this chat, create a new one
    if chat_id not in header_messages:
        return await send_header(bot, chat_id)
    
    try:
        # Получаем все данные для шапки
        today = datetime.datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
        
        # Получаем статистику за день из data_manager
        from data_manager import data_manager
        
        # Получаем полную статистику для этого чата с принудительным обновлением
        stats = data_manager.get_daily_statistics(chat_id, force_refresh=True)
        logging.info(f"Получена статистика для обновления шапки в chat_id {chat_id}: {stats}")
        
        # Проверяем наличие ключей в статистике и устанавливаем значения по умолчанию если их нет
        if not stats or "transactions_count" not in stats:
            logging.warning(f"Статистика для обновления шапки в chat_id {chat_id} пуста или не содержит необходимых ключей")
            stats = {
                "total_amount": 0,
                "awaiting_amount": 0,
                "to_pay_amount": 0,
                "paid_amount": 0,
                "avg_rate": 0,
                "avg_commission": 0,
                "transactions_count": 0,
                "unpaid_usdt": 0,
                "to_pay_usdt": 0,
                "total_usdt": 0,
                "paid_usdt": 0,
                "methods_count": {}
            }
        
        # Получаем текущие настройки и курс обмена
        day_settings = data_manager.get_day_settings(chat_id) or {"rate": 0, "commission_percent": 0}
        current_rate_raw = day_settings.get("rate", 0)
        commission_percent = day_settings.get("commission_percent", 0)
        
        # Обрабатываем курс - извлекаем числовое значение из разных форматов
        # Курс может быть как числом, так и строкой в формате "92.50 USDT" или "92.50₽"
        if isinstance(current_rate_raw, str):
            # Удаляем кавычки и символ рубля, если они есть
            rate_str = current_rate_raw.replace('"', '').replace('₽', '').strip()
            if "USDT" in rate_str:
                # Если уже в формате USDT, извлекаем числовое значение
                current_rate = float(rate_str.replace('USDT', '').strip())
                display_rate = f'"{current_rate:.2f} USDT"'
            else:
                # Если в другом формате, просто преобразуем в число
                current_rate = float(rate_str)
                display_rate = f'"{current_rate:.2f} USDT"'
        else:
            # Если курс числовой
            current_rate = float(current_rate_raw) if current_rate_raw else 0
            if current_rate > 0:
                display_rate = f'"{current_rate:.2f} USDT"'
            else:
                display_rate = "Не установлен"
        
        # Рассчитываем эквивалент в USDT
        # Если курс = 0, используем значение 90 как минимальное для расчетов USDT, чтобы отображать его всегда
        usdt_rate = current_rate if current_rate else 90  # Минимальный курс для отображения USDT
        
        # Получаем статистические данные
        total_amount = stats.get("total_amount", 0)
        awaiting_amount = stats.get("awaiting_amount", 0)
        paid_amount = stats.get("paid_amount", 0)
        to_pay_amount = stats.get("to_pay_amount", 0)
        
        # Получаем значения в USDT, если они есть в статистике, или рассчитываем
        unpaid_usdt = stats.get("unpaid_usdt", round(awaiting_amount / usdt_rate, 1) if usdt_rate > 0 else 0)
        to_pay_usdt = stats.get("to_pay_usdt", round(to_pay_amount / usdt_rate, 1) if usdt_rate > 0 else 0)
        total_usdt = stats.get("total_usdt", round(total_amount / usdt_rate, 1) if usdt_rate > 0 else 0)
        paid_usdt = stats.get("paid_usdt", round(paid_amount / usdt_rate, 1) if usdt_rate > 0 else 0)
        
        # Format the header
        header_text = (
            f"🌠 [OCTOFX] {today}\n\n"
            f"🆔 Айди чата: {chat_id}\n"
            f"🧮 Курс: {display_rate} | Комиссия: {commission_percent}%\n\n"
            f"⚜️ Статистика:\n\n"
            f"⏳ Ожидаем: {awaiting_amount:,.1f}₽ ({unpaid_usdt:.1f} USDT)\n"
            f"💳 К выплате: {to_pay_amount:,.1f}₽ ({to_pay_usdt:.1f} USDT)\n"
            f"💴 Общая сумма: {total_amount:,.1f}₽ ({total_usdt:.1f} USDT)\n\n"
            f"💸 Выплачено: {paid_amount:,.1f}₽ ({paid_usdt:.1f} USDT)\n\n"
            f"Выберите действие из меню ниже"
        )
        
        # Update the header
        message_id = header_messages[chat_id]
        try:
            # Convert chat_id to string to avoid validation error with negative IDs
            chat_id_str = str(chat_id) if isinstance(chat_id, int) else chat_id
            
            await bot.edit_message_text(
                header_text,
                chat_id_str,
                message_id,
                reply_markup=get_main_menu_keyboard()
            )
            return None
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return None
            elif "business connection not found" in str(e).lower():
                logging.error(f"Невозможно обновить сообщение в бизнес-чате: {e}")
                # Мы все равно сохраняем данные в памяти, чтобы статистика обновлялась
                logging.info(f"Статистика успешно обновлена для chat_id {chat_id}")
                return None
            else:
                raise
    except Exception as e:
        logging.error(f"Error updating header: {e}")
        
        # If the message was deleted or otherwise not found, send a new one
        if "message to edit not found" in str(e).lower() or "message can't be edited" in str(e).lower():
            return await send_header(bot, chat_id)
        
        return None


async def register_temp_message(chat_id: int, message_id: int):
    """
    Зарегистрировать временное сообщение для последующего удаления
    
    Args:
        chat_id: ID чата
        message_id: ID сообщения
    """
    # Преобразуем chat_id в строку для консистентности
    chat_id_str = str(chat_id)
    
    if chat_id_str not in temp_messages:
        temp_messages[chat_id_str] = []
    
    # Проверяем, не зарегистрировано ли уже это сообщение
    if message_id not in temp_messages[chat_id_str]:
        temp_messages[chat_id_str].append(message_id)
        logging.debug(f"Registered temp message {message_id} in chat {chat_id_str}")


async def register_input_request(chat_id: int, message_id: int):
    """
    Зарегистрировать сообщение с запросом ввода для последующего удаления
    
    Args:
        chat_id: ID чата
        message_id: ID сообщения
    """
    # Преобразуем chat_id в строку для консистентности
    chat_id_str = str(chat_id)
    
    if chat_id_str not in input_request_messages:
        input_request_messages[chat_id_str] = []
    
    # Проверяем, не зарегистрировано ли уже это сообщение
    if message_id not in input_request_messages[chat_id_str]:
        input_request_messages[chat_id_str].append(message_id)
        logging.debug(f"Registered input request message {message_id} in chat {chat_id_str}")


async def delete_input_requests(bot: Bot, chat_id: int):
    """
    Удалить все сообщения с запросами ввода в чате
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
    """
    # Преобразуем chat_id в строку для консистентности
    chat_id_str = str(chat_id)
    
    if chat_id_str not in input_request_messages or not input_request_messages[chat_id_str]:
        return
    
    deleted_count = 0
    for message_id in input_request_messages[chat_id_str]:
        try:
            await bot.delete_message(chat_id, message_id)
            deleted_count += 1
        except Exception as e:
            logging.warning(f"Ошибка при удалении сообщения с запросом ввода {message_id}: {e}")
    
    # Очистить список сообщений для этого чата
    logging.info(f"Удалено {deleted_count} сообщений с запросами ввода в чате {chat_id}")
    input_request_messages[chat_id_str] = []


async def delete_temp_messages(bot: Bot, chat_id: int):
    """
    Удалить все временные сообщения в чате
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
    """
    # Преобразуем chat_id в строку для консистентности
    chat_id_str = str(chat_id)
    
    if chat_id_str not in temp_messages or not temp_messages[chat_id_str]:
        logging.info(f"No temporary messages to delete in chat {chat_id}")
        return
    
    deleted_count = 0
    for message_id in temp_messages[chat_id_str]:
        try:
            await bot.delete_message(chat_id, message_id)
            deleted_count += 1
        except TelegramBadRequest as e:
            if "message to delete not found" in str(e).lower():
                logging.warning(f"Temporary message {message_id} already deleted")
            else:
                logging.warning(f"Error deleting temporary message {message_id}: {e}")
        except Exception as e:
            logging.warning(f"Error deleting temporary message {message_id}: {e}")
    
    # Очистить список сообщений для этого чата
    logging.info(f"Deleted {deleted_count}/{len(temp_messages[chat_id_str])} temporary messages in chat {chat_id}")
    temp_messages[chat_id_str] = []


async def send_temp_message(bot: Bot, chat_id: int, text: str, **kwargs) -> Optional[Message]:
    """
    Отправить временное сообщение, которое будет удалено при следующей очистке
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        text: Текст сообщения
        **kwargs: Дополнительные параметры для bot.send_message
        
    Returns:
        Optional[Message]: Отправленное сообщение или None в случае ошибки
    """
    try:
        # Добавляем parse_mode='HTML' если не указан
        if 'parse_mode' not in kwargs:
            kwargs['parse_mode'] = 'HTML'
            
        message = await bot.send_message(chat_id, text, **kwargs)
        await register_temp_message(chat_id, message.message_id)
        return message
    except Exception as e:
        logging.error(f"Error sending temporary message: {e}")
        return None


async def register_bot_message(chat_id: int, message_id: int):
    """
    Зарегистрировать обычное сообщение бота для возможности последующей очистки
    
    Args:
        chat_id: ID чата
        message_id: ID сообщения
    """
    # Преобразуем chat_id в строку для консистентности
    chat_id_str = str(chat_id)
    
    if chat_id_str not in bot_messages:
        bot_messages[chat_id_str] = []
    
    # Проверяем, что сообщение еще не зарегистрировано
    if message_id not in bot_messages[chat_id_str]:
        bot_messages[chat_id_str].append(message_id)
        logging.debug(f"Registered bot message {message_id} in chat {chat_id_str}")


async def safe_edit_message_text(callback_query: CallbackQuery, text: str, **kwargs) -> Optional[Message]:
    """
    Безопасно редактирует текст сообщения, игнорируя ошибку о неизмененном сообщении.
    
    Args:
        callback_query: CallbackQuery объект
        text: Новый текст сообщения
        **kwargs: Дополнительные параметры для edit_message_text
        
    Returns:
        Optional[Message]: Отредактированное сообщение или None в случае ошибки
    """
    try:
        # Добавляем parse_mode='HTML' если не указан
        if 'parse_mode' not in kwargs:
            kwargs['parse_mode'] = 'HTML'
        
        message = await callback_query.message.edit_text(text, **kwargs)
        return message
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            # Игнорируем ошибку о неизмененном сообщении
            return None
        else:
            # Другие ошибки пробрасываем дальше
            raise
    except Exception as e:
        logging.error(f"Error editing message: {e}")
        return None


async def send_bot_message(bot: Bot, chat_id: int, text: str, **kwargs) -> Optional[Message]:
    """
    Отправить сообщение от бота и зарегистрировать его для последующей очистки
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        text: Текст сообщения
        **kwargs: Дополнительные параметры для bot.send_message
        
    Returns:
        Optional[Message]: Отправленное сообщение или None в случае ошибки
    """
    try:
        # Добавляем parse_mode='HTML' если не указан
        if 'parse_mode' not in kwargs:
            kwargs['parse_mode'] = 'HTML'
            
        message = await bot.send_message(chat_id, text, **kwargs)
        await register_bot_message(chat_id, message.message_id)
        return message
    except Exception as e:
        logging.error(f"Error sending bot message: {e}")
        return None


async def send_payment_notification(bot: Bot, chat_id: int, text: str, **kwargs) -> Optional[Message]:
    """
    Отправить уведомление о выплате
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        text: Текст сообщения
        **kwargs: Дополнительные параметры для bot.send_message
        
    Returns:
        Optional[Message]: Отправленное сообщение или None в случае ошибки
    """
    try:
        # Добавляем parse_mode='HTML' если не указан
        if 'parse_mode' not in kwargs:
            kwargs['parse_mode'] = 'HTML'
            
        message = await bot.send_message(chat_id, text, **kwargs)
        # Теперь регистрируем уведомления о выплатах для возможности очистки командой /clear
        await register_bot_message(chat_id, message.message_id)
        return message
    except Exception as e:
        logging.error(f"Error sending payment notification: {e}")
        return None


async def try_deep_clean(bot: Bot, chat_id: int, last_message_id: int, limit: int = 100) -> int:
    """
    Попытаться удалить максимальное количество сообщений бота в диапазоне сообщений
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        last_message_id: ID последнего сообщения в чате
        limit: Максимальное количество сообщений для проверки
        
    Returns:
        int: Количество удаленных сообщений
    """
    deleted_count = 0
    # Попробуем удалить сообщения в диапазоне от last_message_id до last_message_id - limit
    # Предполагаем, что ID сообщений идут последовательно
    for message_id in range(last_message_id, max(last_message_id - limit, 1), -1):
        try:
            await bot.delete_message(chat_id, message_id)
            deleted_count += 1
        except TelegramBadRequest as e:
            # Игнорируем сообщения, которые не являются сообщениями бота или не могут быть удалены
            continue
        except Exception as e:
            logging.warning(f"Error deleting message {message_id}: {e}")
            continue
    
    return deleted_count