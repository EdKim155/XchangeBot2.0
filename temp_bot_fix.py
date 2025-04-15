#!/usr/bin/env python3
"""
Временный скрипт для запуска бота с отключенной проверкой SSL.
Используется только для диагностики проблем с подключением.
"""
import asyncio
import logging
import ssl
import os
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv()

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)

# Импортируем токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logging.error("Не найден токен бота в переменных окружения!")
    exit(1)

logging.info(f"Версия aiohttp: {aiohttp.__version__}")
logging.info(f"Версия SSL: {ssl.OPENSSL_VERSION}")

async def main():
    """Основная функция для запуска бота с диагностикой."""
    try:
        # Создаем контекст SSL без проверки сертификатов
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        logging.info("Создан SSL-контекст с отключенной проверкой сертификатов")
        
        # Создаем бота напрямую без AiohttpSession
        bot = Bot(token=BOT_TOKEN, 
                 default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        
        # Вручную настраиваем SSL в сессии бота
        if hasattr(bot, '_session') and hasattr(bot._session, '_connector'):
            if bot._session._connector:
                bot._session._connector._ssl = ssl_context
                logging.info("Вручную настроен SSL для существующего коннектора")
        else:
            logging.warning("Не удалось найти коннектор в сессии бота")
        
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Тестовый запрос к Telegram API
        logging.info("Отправка тестового запроса к API Telegram...")
        try:
            me = await bot.get_me()
            logging.info(f"Успешное соединение с API! Информация о боте: {me.full_name} (@{me.username})")
        except Exception as api_error:
            logging.error(f"Ошибка при соединении с API: {api_error}")
            
            # Попробуем прямой запрос через aiohttp
            logging.info("Пробуем прямой запрос через aiohttp...")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", 
                                          ssl=ssl_context) as response:
                        result = await response.json()
                        logging.info(f"Прямой запрос успешен! Результат: {result}")
            except Exception as direct_error:
                logging.error(f"Ошибка при прямом запросе: {direct_error}")
        
        # Проверка сетевых настроек
        logging.info("Проверка сетевых настроек системы...")
        # Это будет выведено в консоль, но в случае с подключением к API поможет в диагностике
        os.system("ifconfig | grep -E 'inet |flags' | head -10")
        
        logging.info("Тестовый запуск завершен")
    except Exception as e:
        logging.error(f"Ошибка при тестовом запуске: {e}")
    finally:
        # Закрываем сессию если она была создана
        if 'bot' in locals():
            await bot.session.close()
            logging.info("Сессия закрыта.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Тестовый запуск прерван пользователем.")
    except Exception as e:
        logging.error(f"Неожиданная ошибка: {e}") 