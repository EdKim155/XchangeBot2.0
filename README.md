# XchangeBot

Telegram-бот для управления транзакциями и курсами обмена.

## Функциональность

- Отслеживание транзакций
- Управление курсами валют
- Интеграция с Google Sheets
- Статистика и отчеты

## Установка

1. Клонируйте репозиторий
2. Создайте виртуальное окружение: `python -m venv venv`
3. Активируйте окружение: `source venv/bin/activate` (Linux/Mac) или `venv\Scripts\activate` (Windows)
4. Установите зависимости: `pip install -r requirements.txt`
5. Скопируйте `example.env` в `.env` и настройте переменные окружения
6. Запустите бота: `python run.py`

## Переменные окружения

- `BOT_TOKEN` - токен Telegram бота от BotFather
- `ALLOWED_USER_IDS` - список ID пользователей, имеющих доступ
- `GOOGLE_CREDENTIALS_FILE` - путь к файлу учетных данных Google Sheets
- `SPREADSHEET_ID` - ID таблицы Google Sheets
- `SHEET_NAME` - название листа с данными
- `DEBUG` - режим отладки (True/False)
- `SQLALCHEMY_DATABASE_URI` - URI для подключения к базе данных
- `USE_DATABASE` - использовать базу данных или Google Sheets (True/False) 