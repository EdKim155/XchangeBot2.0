import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Bot configuration
# Используем именно токен из .env файла
BOT_TOKEN = os.getenv("BOT_TOKEN")
logging.info(f"Токен бота загружен в config.py: {BOT_TOKEN[:5]}...")

# User access control
ALLOWED_USER_IDS = [int(id) for id in os.getenv("ALLOWED_USER_IDS", "328924878,7232015444,6353711386,7068500266").split(",")]
logging.info(f"Установлен список разрешенных пользователей: {ALLOWED_USER_IDS}")

# Google Sheets configuration
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "xchangebot-fc9c6dfaaf2a.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1lfTZQ25748LrilMakpwv29utuXvy9oOKquSVoD40FPI")
SHEET_NAME = os.getenv("SHEET_NAME", "Transactions")
logging.info(f"Настроено использование Google Sheets с ID: {SPREADSHEET_ID}")
logging.info(f"Файл учетных данных для Google Sheets: {GOOGLE_CREDENTIALS_FILE}")

# Database configuration
DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///bot_database.db")
logging.info(f"База данных настроена: {DATABASE_URL}")

# Data source mode (database or sheets)
USE_DATABASE = os.getenv("USE_DATABASE", "False").lower() in ("true", "1", "yes")
logging.info(f"Источник данных: {'База данных' if USE_DATABASE else 'Google Sheets'}")

# Debug mode
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
