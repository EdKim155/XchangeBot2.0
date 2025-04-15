#!/bin/bash

# Создаем директорию для данных, если её нет
mkdir -p /data

# Создаем Google credentials из переменной окружения, если задана
if [ ! -z "$GOOGLE_CREDENTIALS_JSON" ]; then
    echo "$GOOGLE_CREDENTIALS_JSON" > /data/google_credentials.json
    export GOOGLE_CREDENTIALS_FILE=/data/google_credentials.json
fi

# Настраиваем базу данных на постоянный диск
export SQLALCHEMY_DATABASE_URI=sqlite:////data/bot_database.db

# Запускаем бота
python run.py 