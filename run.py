#!/usr/bin/env python3
"""
Основной файл для запуска Telegram бота.
"""
import asyncio
import logging
import os
import sys
import requests
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logging.error("BOT_TOKEN не найден в переменных окружения")
    sys.exit(1)
logging.info(f"Токен бота загружен из переменных окружения: '{BOT_TOKEN[:5]}...'")

# Функция для проверки подключения к API Telegram
def check_telegram_connection():
    try:
        response = requests.get("https://api.telegram.org", timeout=5)
        if response.status_code == 200:
            logging.info("Подключение к серверам Telegram успешно установлено")
            return True
        else:
            logging.error(f"Ошибка соединения с серверами Telegram. Код ответа: {response.status_code}")
            return False
    except requests.RequestException as e:
        logging.error(f"Ошибка соединения с серверами Telegram: {e}")
        return False

# Проверка доступности API Telegram
if not check_telegram_connection():
    logging.warning("Проблемы с доступом к API Telegram. Пробуем запустить бота в любом случае...")

# Импорт и запуск бота
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

# Проверка валидности токена
def check_token_validity(token):
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            me = response.json().get('result', {})
            logging.info(f"Токен проверен. Бот: @{me.get('username')} (ID: {me.get('id')})")
            return True
        else:
            error = response.json().get('description', 'Ошибка при проверке токена')
            logging.error(f"Неверный токен бота: {error}")
            return False
    except Exception as e:
        logging.error(f"Ошибка при проверке токена: {e}")
        return False

# Проверка валидности токена
if not check_token_validity(BOT_TOKEN):
    logging.error("Токен бота недействителен. Проверьте BOT_TOKEN")
    sys.exit(1)

# Инициализация бота и диспетчера
try:
    logging.info("Инициализация бота...")
    # Создаем сессию с увеличенным таймаутом для лучшей работы с сетью
    session = AiohttpSession(timeout=60)
    bot = Bot(token=BOT_TOKEN, 
              session=session,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logging.info("Бот успешно инициализирован")
except Exception as e:
    logging.error(f"Ошибка при инициализации бота: {e}")
    sys.exit(1)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def main():
    """Основная функция для запуска бота."""
    # Регистрация мидлвары
    from middlewares import register_middlewares
    register_middlewares(dp)
    
    # Регистрация обработчиков
    from handlers import register_handlers
    register_handlers(dp)
    
    # Установка команд в боковом меню
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота / Открыть меню")
    ])
    
    # Запуск бота с автоматической повторной попыткой при проблемах с соединением
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logging.info("Запуск бота...")
            await dp.start_polling(bot)
            break  # Если успешно, выходим из цикла
        except Exception as e:
            retry_count += 1
            logging.error(f"Ошибка соединения с Telegram API: {e}")
            if retry_count < max_retries:
                wait_time = 5 * retry_count
                logging.info(f"Повторная попытка через {wait_time} секунд... (Попытка {retry_count}/{max_retries})")
                await asyncio.sleep(wait_time)
            else:
                logging.error("Достигнуто максимальное количество попыток. Выход.")
                raise
    
    try:
        # Держим бота запущенным
        await asyncio.Event().wait()
    finally:
        logging.info("Бот остановлен.")
        await bot.session.close()

if __name__ == "__main__":
    try:
        logging.info("Старт Telegram бота...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем.")
    except Exception as e:
        logging.error(f"Неожиданная ошибка: {e}")
        sys.exit(1)