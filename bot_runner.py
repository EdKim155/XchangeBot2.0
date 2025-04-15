#!/usr/bin/env python3
"""
Скрипт для запуска Telegram бота в Replit.
"""
import logging
import os
import signal
import sys
import time
import subprocess

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)

# Обработчик сигналов
def signal_handler(sig, frame):
    logging.info("Получен сигнал завершения. Завершение работы...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Основная функция для запуска бота."""
    logging.info("Запуск Telegram бота...")
    
    # Запускаем бот с помощью run.py
    while True:
        try:
            process = subprocess.Popen(
                ["python3", "run.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Читаем вывод процесса
            while process.poll() is None:
                line = process.stdout.readline()
                if line:
                    print(line, end="")
                
            # Ждем завершения процесса
            process.wait()
            
            if process.returncode != 0:
                logging.error(f"Бот завершился с кодом {process.returncode}. Перезапуск через 5 секунд...")
                time.sleep(5)
            else:
                logging.info("Бот завершил работу нормально.")
                break
                
        except Exception as e:
            logging.error(f"Ошибка при запуске бота: {e}. Перезапуск через 5 секунд...")
            time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем.")
    except Exception as e:
        logging.error(f"Необработанная ошибка: {e}")
        sys.exit(1)