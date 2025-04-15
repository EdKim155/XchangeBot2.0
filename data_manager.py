import logging
import os
from typing import Dict, List, Optional, Union, Any

from database import db_manager
from sheets import sheets_client

# Определяем, какой источник данных использовать
USE_DATABASE = os.getenv("USE_DATABASE", "False").lower() in ("true", "1", "yes")

class DataManager:
    """
    Универсальный менеджер данных, который абстрагирует работу с источниками данных.
    Может использовать либо базу данных, либо Google Sheets в зависимости от настроек.
    """
    
    def __init__(self):
        """Инициализация менеджера данных."""
        self.data_source = "database" if USE_DATABASE else "sheets"
        self.stats_cache = {}  # Добавляем инициализацию кэша статистики
        logging.info(f"Инициализация DataManager с источником данных: {self.data_source}")
    
    def get_day_settings(self, chat_id: int) -> Optional[Dict[str, Union[str, float]]]:
        """
        Получить настройки дня для чата.
        
        Args:
            chat_id: ID чата
            
        Returns:
            Optional[Dict]: Настройки дня или None если не найдены
        """
        if self.data_source == "database":
            return db_manager.get_day_settings(chat_id)
        else:
            # В случае с Google Sheets передаем chat_id для фильтрации
            return sheets_client.get_day_settings(chat_id)
    
    def is_day_open(self, chat_id: int) -> bool:
        """
        Проверить, открыт ли день для чата.
        
        Args:
            chat_id: ID чата
            
        Returns:
            bool: True если день открыт, False если нет
        """
        if self.data_source == "database":
            return db_manager.is_day_open(chat_id)
        else:
            return sheets_client.is_day_open(chat_id)
    
    def set_day_status(self, chat_id: int, is_open: bool) -> bool:
        """
        Установить статус дня для чата.
        
        Args:
            chat_id: ID чата
            is_open: Открыт ли день
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        if self.data_source == "database":
            return db_manager.set_day_status(chat_id, is_open)
        else:
            return sheets_client.set_day_status(is_open, chat_id)
    
    def save_day_settings(self, chat_id: int, rate: float, commission_percent: float) -> bool:
        """
        Сохранить настройки дня для чата.
        
        Args:
            chat_id: ID чата
            rate: Курс обмена
            commission_percent: Процент комиссии
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        if self.data_source == "database":
            return db_manager.save_day_settings(chat_id, rate, commission_percent)
        else:
            return sheets_client.save_day_settings(rate, commission_percent, chat_id)
    
    def add_transaction(self, chat_id: int, data: Dict[str, Any]) -> int:
        """
        Добавить новую транзакцию для чата.
        
        Args:
            chat_id: ID чата
            data: Словарь с данными транзакции
            
        Returns:
            int: ID добавленной транзакции
        """
        if self.data_source == "database":
            return db_manager.add_transaction(chat_id, data)
        else:
            # В случае с Google Sheets добавляем chat_id в данные транзакции как идентификатор группы
            # Сохраняем название группы (если есть) в поле group, а chat_id в поле chat_id
            data["chat_id"] = str(chat_id)
            # Если в данных уже есть название группы, используем его, иначе используем chat_id как резерв
            if "group" not in data or not data["group"]:
                data["group"] = str(chat_id)
            
            return sheets_client.add_transaction(data)
    
    def update_transaction(self, transaction_id: int, data: Dict[str, Any]) -> bool:
        """
        Обновить существующую транзакцию.
        
        Args:
            transaction_id: ID транзакции
            data: Словарь с обновленными данными
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        if self.data_source == "database":
            return db_manager.update_transaction(transaction_id, data)
        else:
            return sheets_client.update_transaction(transaction_id, data)
    
    def get_transaction(self, transaction_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить транзакцию по ID.
        
        Args:
            transaction_id: ID транзакции
            
        Returns:
            Optional[Dict]: Данные транзакции или None если не найдена
        """
        if self.data_source == "database":
            return db_manager.get_transaction(transaction_id)
        else:
            return sheets_client.get_transaction(transaction_id)
    
    def get_all_transactions(self, chat_id: int, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получить все транзакции для чата (опционально за указанную дату).
        
        Args:
            chat_id: ID чата
            date: Опциональная дата в формате DD.MM.YYYY
            
        Returns:
            List[Dict]: Список словарей с данными транзакций
        """
        # Если дата не указана, используем текущую дату
        if not date:
            from datetime import datetime
            from sheets import MSK_TIMEZONE
            date = datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
            logging.info(f"Используем текущую дату: {date}")
        
        if self.data_source == "database":
            return db_manager.get_daily_transactions(chat_id)
        else:
            # Для Google Sheets получаем все транзакции за указанную дату и фильтруем по chat_id
            logging.info(f"Получаем транзакции за дату {date}")
            all_transactions = sheets_client.get_all_transactions(date=date, force_refresh=True)
            
            # Фильтруем по chat_id (числовому) или по названию группы (chat_id как строка)
            str_chat_id = str(chat_id)
            
            # Проверяем группу и chat_id
            filtered_transactions = []
            for t in all_transactions:
                # Проверяем chat_id (приоритетно)
                if str(t.get('chat_id', '')) == str_chat_id:
                    filtered_transactions.append(t)
                    continue
                    
                # Также проверяем поле group
                if str(t.get('group', '')) == str_chat_id:
                    # Если совпало по группе, обновляем chat_id для будущей фильтрации
                    t['chat_id'] = str_chat_id
                    filtered_transactions.append(t)
            
            logging.info(f"Получено {len(filtered_transactions)} транзакций за {date} для чата {chat_id}")
            return filtered_transactions
    
    def get_daily_transactions(self, chat_id: int) -> List[Dict[str, Any]]:
        """
        Получить все транзакции для чата за текущий день.
        
        Args:
            chat_id: ID чата
            
        Returns:
            List[Dict]: Список словарей с данными транзакций
        """
        if self.data_source == "database":
            return db_manager.get_daily_transactions(chat_id)
        else:
            # Для Google Sheets получаем все дневные транзакции и фильтруем по chat_id
            daily_transactions = sheets_client.get_daily_transactions(force_refresh=True)
            str_chat_id = str(chat_id)
            
            # Проверяем группу и chat_id
            filtered_transactions = []
            for t in daily_transactions:
                # Проверяем chat_id (приоритетно)
                if str(t.get('chat_id', '')) == str_chat_id:
                    filtered_transactions.append(t)
                    continue
                    
                # Также проверяем поле group
                if str(t.get('group', '')) == str_chat_id:
                    # Если совпало по группе, обновляем chat_id для будущей фильтрации
                    t['chat_id'] = str_chat_id
                    filtered_transactions.append(t)
            
            logging.info(f"Получено {len(filtered_transactions)} транзакций за текущий день для чата {chat_id}")
            return filtered_transactions
    
    def get_unpaid_transactions(self, chat_id: int) -> List[Dict[str, Any]]:
        """
        Получить все неоплаченные транзакции для чата.
        
        Args:
            chat_id: ID чата
            
        Returns:
            List[Dict]: Список словарей с данными неоплаченных транзакций
        """
        if self.data_source == "database":
            return db_manager.get_unpaid_transactions(chat_id)
        else:
            # Для Google Sheets получаем все неоплаченные транзакции и фильтруем по chat_id
            unpaid_transactions = sheets_client.get_unpaid_transactions(force_refresh=True)
            str_chat_id = str(chat_id)
            
            # Проверяем группу и chat_id
            filtered_transactions = []
            for t in unpaid_transactions:
                # Проверяем chat_id (приоритетно)
                if str(t.get('chat_id', '')) == str_chat_id:
                    filtered_transactions.append(t)
                    continue
                    
                # Также проверяем поле group
                if str(t.get('group', '')) == str_chat_id:
                    # Если совпало по группе, обновляем chat_id для будущей фильтрации
                    t['chat_id'] = str_chat_id
                    filtered_transactions.append(t)
            
            logging.info(f"Получено {len(filtered_transactions)} неоплаченных транзакций для чата {chat_id}")
            return filtered_transactions
    
    def mark_transaction_paid(self, transaction_id: int, transaction_hash: str) -> bool:
        """
        Отметить транзакцию как оплаченную.
        
        Args:
            transaction_id: ID транзакции
            transaction_hash: Хеш транзакции
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        if self.data_source == "database":
            return db_manager.mark_transaction_paid(transaction_id, transaction_hash)
        else:
            return sheets_client.mark_transaction_paid(transaction_id, transaction_hash)
    
    def get_current_rate(self, chat_id: int) -> Optional[float]:
        """
        Получить текущий курс обмена для чата.
        
        Args:
            chat_id: ID чата
            
        Returns:
            Optional[float]: Текущий курс или None если не найден
        """
        if self.data_source == "database":
            return db_manager.get_current_rate(chat_id)
        else:
            return sheets_client.get_current_rate(chat_id)
    
    def get_daily_statistics(self, chat_id: int, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Получить полную статистику для чата за текущий день.
        
        Args:
            chat_id: ID чата
            force_refresh: Принудительно обновить данные из источника, минуя кеш
            
        Returns:
            Dict[str, Any]: Словарь со статистикой
        """
        # Сначала проверим кэш, если нет принудительного обновления
        cache_key = f"day_stats_{chat_id}"
        if not force_refresh and cache_key in self.stats_cache:
            logging.info(f"Используем кешированную статистику для чата {chat_id}")
            return self.stats_cache[cache_key]
        
        logging.info(f"Получаем статистику для чата {chat_id} с force_refresh={force_refresh}")
        
        if self.data_source == "database":
            # Получаем статистику из базы данных с принудительным обновлением
            result = db_manager.get_daily_statistics(chat_id, force_refresh=force_refresh)
            logging.info(f"Получена статистика из базы данных для чата {chat_id}: {result}")
        else:
            # Получаем статистику из Google Sheets с принудительным обновлением
            result = sheets_client.get_daily_statistics(chat_id, force_refresh=force_refresh)
            logging.info(f"Получена статистика из Google Sheets для чата {chat_id}: {result}")
            
        # Обновляем кэш, даже если это было принудительное обновление
        self.stats_cache[cache_key] = result
        logging.info(f"Обновлен кэш статистики для чата {chat_id}")
        
        return result
    
    def clear_stats_cache(self, chat_id: int) -> None:
        """
        Очищает кэш статистики для указанного чата.
        
        Args:
            chat_id: ID чата
        """
        if chat_id in self.stats_cache:
            del self.stats_cache[chat_id]
            logging.info(f"Cleared statistics cache for chat {chat_id}")

# Создаем глобальный экземпляр менеджера данных
data_manager = DataManager()