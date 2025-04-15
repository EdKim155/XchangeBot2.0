#!/usr/bin/env python3
"""
Основной файл для интеграции с Replit.
При запуске main.py через gunicorn, предоставляется информация о боте.
"""
import os
import sys
import logging
import subprocess
import time
import signal
import threading

from flask import Flask
from models import db
from config import DATABASE_URL

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)

# Глобальная переменная для хранения процесса бота
bot_process = None
bot_thread = None

def start_bot_process():
    """Запускает бота в отдельном процессе"""
    global bot_process
    
    # Запускаем бота в отдельном процессе
    logging.info("Запуск процесса бота...")
    bot_process = subprocess.Popen(["python", "bot_daemon.py"])
    logging.info(f"Бот запущен с PID: {bot_process.pid}")
    return bot_process.pid

def monitor_bot_process():
    """Мониторит процесс бота и перезапускает его при необходимости"""
    global bot_process
    
    while True:
        # Проверяем статус процесса
        if bot_process and bot_process.poll() is not None:
            logging.warning(f"Процесс бота завершился с кодом: {bot_process.returncode}")
            logging.info("Перезапуск бота...")
            start_bot_process()
        
        time.sleep(10)  # Проверяем каждые 10 секунд

# Инициализация Flask приложения для работы с базой данных
flask_app = Flask(__name__)
flask_app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(flask_app)

# Создание таблиц базы данных
with flask_app.app_context():
    db.create_all()
    logging.info("Таблицы в базе данных созданы")

# WSGI приложение для интеграции с gunicorn
def app(environ, start_response):
    """WSGI приложение для запуска и мониторинга бота"""
    global bot_process, bot_thread
    
    if not bot_process or bot_process.poll() is not None:
        # Запускаем бота если он не запущен
        start_bot_process()
    
    if not bot_thread or not bot_thread.is_alive():
        # Запускаем мониторинг в отдельном потоке
        bot_thread = threading.Thread(target=monitor_bot_process)
        bot_thread.daemon = True
        bot_thread.start()
        logging.info("Запущен поток мониторинга бота")
    
    # Отправляем информацию о статусе бота
    status = "running" if bot_process and bot_process.poll() is None else "stopped"
    pid = bot_process.pid if bot_process else "N/A"
    response_body = f"Telegram bot status: {status}, PID: {pid}"
    
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [response_body.encode('utf-8')]

if __name__ == "__main__":
    # Запускаем бота напрямую, если скрипт запущен как основной
    pid = start_bot_process()
    
    try:
        # Ждем завершения процесса
        bot_process.wait()
    except KeyboardInterrupt:
        # Корректно завершаем процесс при нажатии Ctrl+C
        logging.info("Остановка бота по запросу пользователя...")
        if bot_process:
            bot_process.terminate()
            bot_process.wait()
        logging.info("Бот остановлен.")
