import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, Union

import pytz
from sqlalchemy import desc
from flask import Flask

from models import db, ChatSettings, Transaction
from config import DATABASE_URL

# Московское время (UTC+3)
MSK_TIMEZONE = pytz.timezone('Europe/Moscow')

# Инициализация Flask приложения для работы с базой данных
flask_app = Flask(__name__)
flask_app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(flask_app)

# Создание таблиц базы данных
with flask_app.app_context():
    db.create_all()
    logging.info("Таблицы в базе данных созданы или уже существуют")

class DatabaseManager:
    """Менеджер для работы с базой данных и обеспечения совместимости с предыдущим API Google Sheets."""

    def __init__(self):
        """Инициализация менеджера базы данных."""
        self.app = flask_app
        logging.info("Инициализация DatabaseManager")

    def get_or_create_chat_settings(self, chat_id: int, chat_name: str = None) -> ChatSettings:
        """
        Получить или создать настройки чата.
        Используются глобальные настройки для всех чатов.
        
        Args:
            chat_id: ID чата (используется только для совместимости)
            chat_name: Имя чата (опционально)
            
        Returns:
            ChatSettings: Объект с настройками чата
        """
        # Используем контекст приложения Flask для работы с базой данных
        with self.app.app_context():
            # Получаем первую запись в таблице настроек, не фильтруя по chat_id
            settings = ChatSettings.query.first()
            
            if not settings:
                logging.info("Создание глобальных настроек")
                # Используем фиксированный ID для глобальных настроек
                settings = ChatSettings(
                    chat_id=1,  # Фиксированный ID для глобальных настроек
                    chat_name="Global Settings",
                    exchange_rate=0.0,
                    commission_percent=0.0,
                    is_day_open=False
                )
                db.session.add(settings)
                db.session.commit()
            
            return settings

    def update_chat_settings(self, chat_id: int, **kwargs) -> bool:
        """
        Обновить настройки чата.
        
        Args:
            chat_id: ID чата
            **kwargs: Параметры для обновления
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        try:
            settings = self.get_or_create_chat_settings(chat_id)
            
            if 'exchange_rate' in kwargs:
                settings.exchange_rate = float(kwargs['exchange_rate'])
            if 'commission_percent' in kwargs:
                settings.commission_percent = float(kwargs['commission_percent'])
            if 'is_day_open' in kwargs:
                settings.is_day_open = bool(kwargs['is_day_open'])
            if 'chat_name' in kwargs and kwargs['chat_name']:
                settings.chat_name = kwargs['chat_name']
            
            settings.updated_at = datetime.now(MSK_TIMEZONE)
            db.session.commit()
            
            logging.info(f"Обновлены настройки чата {chat_id}")
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Ошибка при обновлении настроек чата {chat_id}: {e}")
            return False

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
        return self.update_chat_settings(
            chat_id,
            exchange_rate=rate,
            commission_percent=commission_percent,
            is_day_open=True
        )

    def get_day_settings(self, chat_id: int) -> Optional[Dict[str, Union[str, float]]]:
        """
        Получить настройки дня для чата.
        
        Args:
            chat_id: ID чата
            
        Returns:
            Optional[Dict]: Настройки дня или None если не найдены
        """
        with self.app.app_context():
            # Используем глобальные настройки вместо фильтрации по чату
            settings = ChatSettings.query.first()
            
            if not settings:
                return None
            
            return {
                "date": datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y"),
                "rate": settings.exchange_rate,
                "commission_percent": settings.commission_percent,
                "is_open": settings.is_day_open
            }

    def is_day_open(self, chat_id: int) -> bool:
        """
        Проверить, открыт ли день для чата.
        
        Args:
            chat_id: ID чата
            
        Returns:
            bool: True если день открыт, False если нет
        """
        with self.app.app_context():
            # Используем глобальные настройки вместо фильтрации по чату
            settings = ChatSettings.query.first()
            return settings.is_day_open if settings else False

    def set_day_status(self, chat_id: int, is_open: bool) -> bool:
        """
        Установить статус дня для чата.
        
        Args:
            chat_id: ID чата
            is_open: Открыт ли день
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        return self.update_chat_settings(chat_id, is_day_open=is_open)

    def add_transaction(self, chat_id: int, data: Dict[str, Any]) -> int:
        """
        Добавить новую транзакцию для чата.
        
        Args:
            chat_id: ID чата
            data: Словарь с данными транзакции
            
        Returns:
            int: ID добавленной транзакции
        """
        with self.app.app_context():
            try:
                # Конвертация строковых значений в числа, если необходимо
                amount = data.get("amount", 0)
                if isinstance(amount, str):
                    amount = int(amount.replace(" ", "").replace("₽", ""))
                
                commission = data.get("commission", 0)
                if isinstance(commission, str):
                    commission = float(commission.replace("%", ""))
                
                rate = data.get("rate", 0)
                if isinstance(rate, str):
                    rate = float(rate.replace("₽", ""))
                
                # Создание новой транзакции
                transaction = Transaction(
                    chat_id=chat_id,
                    amount=amount,
                    method=data.get("method", ""),
                    commission=commission,
                    rate=rate,
                    status="Не выплачено",  # Всегда устанавливаем статус "Не выплачено" для новых сделок
                    transaction_hash=data.get("hash", "")
                )
                
                db.session.add(transaction)
                db.session.commit()
                
                logging.info(f"Добавлена транзакция {transaction.id} в базу данных")
                return transaction.id
            
            except Exception as e:
                db.session.rollback()
                logging.error(f"Ошибка при добавлении транзакции: {e}")
                raise

    def update_transaction(self, transaction_id: int, data: Dict[str, Any]) -> bool:
        """
        Обновить существующую транзакцию.
        
        Args:
            transaction_id: ID транзакции
            data: Словарь с обновленными данными
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        with self.app.app_context():
            try:
                transaction = Transaction.query.get(transaction_id)
                
                if not transaction:
                    logging.error(f"Транзакция с ID {transaction_id} не найдена")
                    return False
                
                # Обновление полей
                if "amount" in data:
                    amount = data["amount"]
                    if isinstance(amount, str):
                        amount = int(amount.replace(" ", "").replace("₽", ""))
                    transaction.amount = amount
                
                if "method" in data:
                    transaction.method = data["method"]
                
                if "commission" in data:
                    commission = data["commission"]
                    if isinstance(commission, str):
                        commission = float(commission.replace("%", ""))
                    transaction.commission = commission
                
                if "rate" in data:
                    rate = data["rate"]
                    if isinstance(rate, str):
                        rate = float(rate.replace("₽", ""))
                    transaction.rate = rate
                
                if "status" in data:
                    transaction.status = data["status"]
                
                if "hash" in data:
                    transaction.transaction_hash = data["hash"]
                
                transaction.updated_at = datetime.now(MSK_TIMEZONE)
                db.session.commit()
                
                logging.info(f"Обновлена транзакция {transaction_id} в базе данных")
                return True
            
            except Exception as e:
                db.session.rollback()
                logging.error(f"Ошибка при обновлении транзакции {transaction_id}: {e}")
                return False

    def get_transaction(self, transaction_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить транзакцию по ID.
        
        Args:
            transaction_id: ID транзакции
            
        Returns:
            Optional[Dict]: Данные транзакции или None если не найдена
        """
        with self.app.app_context():
            try:
                transaction = Transaction.query.get(transaction_id)
                
                if not transaction:
                    return None
                
                return transaction.to_dict()
            
            except Exception as e:
                logging.error(f"Ошибка при получении транзакции {transaction_id}: {e}")
                return None

    def get_all_transactions(self, chat_id: int, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получить все транзакции для чата, опционально отфильтрованные по дате.
        
        Args:
            chat_id: ID чата
            date: Опциональная дата в формате DD.MM.YYYY
            
        Returns:
            List[Dict]: Список словарей с данными транзакций
        """
        with self.app.app_context():
            try:
                query = Transaction.query.filter_by(chat_id=chat_id)
                
                if date:
                    # Фильтрация по дате (в формате DD.MM.YYYY)
                    # Это сложнее, так как мы храним datetime в базе
                    # Нам нужно сконвертировать дату в диапазон datetime
                    day, month, year = map(int, date.split('.'))
                    start_date = datetime(year, month, day, 0, 0, 0, tzinfo=MSK_TIMEZONE)
                    end_date = datetime(year, month, day, 23, 59, 59, tzinfo=MSK_TIMEZONE)
                    
                    query = query.filter(Transaction.created_at.between(start_date, end_date))
                
                transactions = query.order_by(desc(Transaction.created_at)).all()
                
                return [transaction.to_dict() for transaction in transactions]
            
            except Exception as e:
                logging.error(f"Ошибка при получении транзакций для чата {chat_id}: {e}")
                return []

    def get_daily_transactions(self, chat_id: int) -> List[Dict[str, Any]]:
        """
        Получить все транзакции для чата за текущий день.
        
        Args:
            chat_id: ID чата
            
        Returns:
            List[Dict]: Список словарей с данными транзакций
        """
        with self.app.app_context():
            current_date = datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
            return self.get_all_transactions(chat_id, date=current_date)

    def get_unpaid_transactions(self, chat_id: int) -> List[Dict[str, Any]]:
        """
        Получить все неоплаченные транзакции для чата.
        
        Args:
            chat_id: ID чата
            
        Returns:
            List[Dict]: Список словарей с данными неоплаченных транзакций
        """
        with self.app.app_context():
            try:
                transactions = Transaction.query.filter_by(chat_id=chat_id, status="Не выплачено").all()
                return [transaction.to_dict() for transaction in transactions]
            
            except Exception as e:
                logging.error(f"Ошибка при получении неоплаченных транзакций для чата {chat_id}: {e}")
                return []

    def mark_transaction_paid(self, transaction_id: int, transaction_hash: str) -> bool:
        """
        Отметить транзакцию как оплаченную.
        
        Args:
            transaction_id: ID транзакции
            transaction_hash: Хеш транзакции
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        with self.app.app_context():
            return self.update_transaction(
                transaction_id,
                {
                    "status": "Выплачено",
                    "hash": transaction_hash
                }
            )

    def get_current_rate(self, chat_id: int) -> Optional[float]:
        """
        Получить текущий курс обмена для чата.
        
        Args:
            chat_id: ID чата
            
        Returns:
            Optional[float]: Текущий курс или None если нет транзакций
        """
        with self.app.app_context():
            # Используем глобальные настройки вместо фильтрации по чату
            settings = ChatSettings.query.first()
            
            if settings and settings.exchange_rate:
                return settings.exchange_rate
            
            # Если не задан в настройках, попробуем взять из последней транзакции
            try:
                # Получаем последнюю транзакцию из любого чата
                latest_transaction = Transaction.query.order_by(desc(Transaction.created_at)).first()
                
                if latest_transaction and latest_transaction.rate:
                    return latest_transaction.rate
            
            except Exception as e:
                logging.error(f"Ошибка при получении текущего курса: {e}")
            
            return None

    def get_daily_statistics(self, chat_id: int, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Получает статистику по транзакциям за текущий день для чата
        
        Args:
            chat_id (int): ID чата
            force_refresh (bool): Принудительно обновить кэш
            
        Returns:
            dict: Статистические данные
        """
        try:
            with self.app.app_context() as session:
                # Получаем дату в MSK timezone
                current_date = datetime.now(MSK_TIMEZONE).strftime("%d.%m.%Y")
                
                # Получаем транзакции за текущий день для указанного чата
                query = session.query(Transaction).filter(
                    Transaction.date == current_date,
                    Transaction.chat_id == chat_id
                )
                transactions = query.all()
                
                if not transactions:
                    empty_stats = {
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
                        "paid_usdt": 0
                    }
                    return empty_stats
                
                # Получаем настройки дня для текущего чата
                day_settings = session.query(ChatSettings).filter(
                    ChatSettings.chat_id == chat_id,
                    ChatSettings.date == current_date
                ).first()
                
                current_rate = day_settings.exchange_rate if day_settings else 0
                current_commission = day_settings.commission_percent if day_settings else 0
                
                # Счетчики для статистики
                total_amount = 0
                awaiting_amount = 0
                to_pay_amount = 0
                paid_amount = 0
                rates_sum = 0
                rates_count = 0
                commission_sum = 0
                commission_count = 0
                
                # Рассчитываем статистику по каждой транзакции
                for tx in transactions:
                    try:
                        # Получаем сумму
                        amount = tx.amount
                        
                        # Добавляем к общей сумме
                        total_amount += amount
                        
                        # Получаем курс и комиссию
                        rate = tx.rate if tx.rate else current_rate
                        commission = tx.commission if tx.commission is not None else current_commission
                        
                        # Учитываем для расчета средних значений
                        if rate:
                            rates_sum += rate
                            rates_count += 1
                        
                        if commission is not None:
                            commission_sum += commission
                            commission_count += 1
                        
                        # Распределяем по статусам
                        status = tx.status.lower() if tx.status else ''
                        if status == 'paid' or status == 'оплачено' or status == 'выплачено':
                            paid_amount += amount
                        else:  # 'awaiting', 'не выплачено', 'к выплате' или другие статусы
                            awaiting_amount += amount
                            
                            # Рассчитываем сумму к выплате с учетом индивидуальной комиссии
                            tx_commission = commission if commission is not None else current_commission
                            to_pay_amount += amount * (1 - tx_commission / 100)
                    except Exception as e:
                        logging.error(f"Error processing transaction for statistics: {e}, transaction ID: {tx.id}")
                        continue
                
                # Рассчитываем средние значения
                avg_rate = rates_sum / rates_count if rates_count > 0 else current_rate
                avg_commission = commission_sum / commission_count if commission_count > 0 else current_commission
                
                # Используем текущий курс, если доступен, иначе средний курс
                usdt_rate = current_rate if current_rate > 0 else (avg_rate if avg_rate > 0 else 90)
                
                # Рассчитываем эквиваленты в USDT
                unpaid_usdt = round(awaiting_amount / usdt_rate, 2) if usdt_rate > 0 else 0
                to_pay_usdt = round(to_pay_amount / usdt_rate, 2) if usdt_rate > 0 else 0
                total_usdt = round(total_amount / usdt_rate, 2) if usdt_rate > 0 else 0
                paid_usdt = round(paid_amount / usdt_rate, 2) if usdt_rate > 0 else 0
                
                # Результат
                result = {
                    "total_amount": total_amount,
                    "awaiting_amount": awaiting_amount,
                    "to_pay_amount": to_pay_amount,
                    "paid_amount": paid_amount,
                    "avg_rate": avg_rate,
                    "avg_commission": avg_commission,
                    "transactions_count": len(transactions),
                    "unpaid_usdt": unpaid_usdt,
                    "to_pay_usdt": to_pay_usdt,
                    "total_usdt": total_usdt,
                    "paid_usdt": paid_usdt
                }
                
                return result
        except Exception as e:
            logging.error(f"Error getting daily statistics from database: {e}")
            return {
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
                "paid_usdt": 0
            }

# Инициализация менеджера базы данных
db_manager = DatabaseManager()