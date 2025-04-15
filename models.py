from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

# Московское время (UTC+3)
MSK_TIMEZONE = pytz.timezone('Europe/Moscow')

db = SQLAlchemy()

class ChatSettings(db.Model):
    """Модель для хранения настроек каждого чата."""
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    chat_name = db.Column(db.String(255), nullable=True)
    exchange_rate = db.Column(db.Float, nullable=False, default=0.0)
    commission_percent = db.Column(db.Float, nullable=False, default=0.0)
    is_day_open = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MSK_TIMEZONE))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(MSK_TIMEZONE), 
                           onupdate=lambda: datetime.now(MSK_TIMEZONE))

    def __repr__(self):
        return f"<ChatSettings chat_id={self.chat_id}, rate={self.exchange_rate}, commission={self.commission_percent}>"


class Transaction(db.Model):
    """Модель для хранения транзакций для каждого чата."""
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.BigInteger, nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String(50), nullable=False)
    commission = db.Column(db.Float, nullable=False, default=0.0)
    rate = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default="Не выплачено")
    transaction_hash = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MSK_TIMEZONE))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(MSK_TIMEZONE), 
                           onupdate=lambda: datetime.now(MSK_TIMEZONE))

    def __repr__(self):
        return f"<Transaction id={self.id}, chat_id={self.chat_id}, amount={self.amount}, status={self.status}>"

    def to_dict(self):
        """Преобразовать транзакцию в словарь (аналогично Google Sheets API)."""
        return {
            "id": self.id,
            "datetime": self.created_at.strftime("%d.%m.%Y %H:%M:%S"),
            "amount": self.amount,
            "method": self.method,
            "commission": self.commission,
            "rate": self.rate,
            "status": self.status,
            "group": str(self.chat_id),
            "hash": self.transaction_hash or ""
        }