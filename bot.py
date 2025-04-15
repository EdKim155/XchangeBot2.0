import asyncio
import logging
import os
import sys
import time
import signal
import threading
from dotenv import load_dotenv

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)

# Load environment variables
load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN, DEBUG

# Initialize bot with custom session for better connection handling
# Fix for SSL connectivity issues
import ssl
import aiohttp
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False  # Отключаем проверку имени хоста
ssl_context.verify_mode = ssl.CERT_NONE  # Отключаем проверку сертификата
connector = aiohttp.TCPConnector(ssl=ssl_context)

session = AiohttpSession(timeout=60)
# Установка SSL-контекста в коннекторе после создания сессии
session._connector._ssl = ssl_context
logging.info("Настроен SSL-контекст с отключенной проверкой сертификатов")

bot = Bot(token=BOT_TOKEN, 
          default=DefaultBotProperties(parse_mode=ParseMode.HTML),
          session=session)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


async def main():
    """Main function to start the bot."""
    # Register middlewares
    try:
        logging.info("Registering middlewares...")
        from middlewares import register_middlewares
        register_middlewares(dp)
        logging.info("Middlewares registered successfully")
    except Exception as e:
        logging.error(f"Error registering middlewares: {e}")
        raise
    
    # Register handlers
    try:
        logging.info("Registering handlers...")
        from handlers import register_handlers
        register_handlers(dp)
        logging.info("Handlers registered successfully")
    except Exception as e:
        logging.error(f"Error registering handlers: {e}")
        raise
    
    # Set up the bot's commands for the side menu
    try:
        logging.info("Setting up bot commands...")
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="start", description="Запустить бота / Открыть меню")
        ])
        logging.info("Bot commands set up successfully")
    except Exception as e:
        logging.error(f"Error setting up bot commands: {e}")
        raise
    
    # Start the bot with reconnection on network errors
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logging.info("Starting bot polling...")
            await dp.start_polling(bot)
            logging.info("Bot polling started successfully")
            break  # Если успешно, выходим из цикла
        except Exception as e:
            retry_count += 1
            logging.error(f"Error connecting to Telegram API: {e}")
            if retry_count < max_retries:
                wait_time = 5 * retry_count  # Постепенно увеличиваем время ожидания
                logging.info(f"Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                await asyncio.sleep(wait_time)
            else:
                logging.error("Maximum retry attempts reached. Exiting.")
                raise
    
    try:
        logging.info("Bot is running. Press Ctrl+C to stop.")
        # Держим бота запущенным
        await asyncio.Event().wait()  # Бесконечное ожидание
    finally:
        logging.info("Bot stopped.")
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot shutdown.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)
