#!/usr/bin/env python3
import re

# Путь к файлу
file_path = 'utils/message_utils.py'

# Прочитать содержимое файла
with open(file_path, 'r', encoding='utf-8') as file:
    content = file.read()

# Замена для всех вхождений
replaced_content = re.sub(
    r'# Считаем неоплаченные и оплаченные суммы\n        unpaid_transactions = sheets_client\.get_unpaid_transactions\(\)',
    '# Считаем неоплаченные и оплаченные суммы с принудительным обновлением кэша\n        unpaid_transactions = sheets_client.get_unpaid_transactions(force_refresh=True)', 
    content
)

replaced_content = re.sub(
    r'# Текущий курс и комиссия\n        current_rate = sheets_client\.get_current_rate\(\)',
    '# Текущий курс и комиссия с принудительным обновлением кэша\n        current_rate = sheets_client.get_current_rate(force_refresh=True)', 
    replaced_content
)

replaced_content = re.sub(
    r'day_settings = sheets_client\.get_day_settings\(\)',
    'day_settings = sheets_client.get_day_settings(force_refresh=True)', 
    replaced_content
)

# Записать обновленное содержимое в файл
with open(file_path, 'w', encoding='utf-8') as file:
    file.write(replaced_content)

print("Обновление файла завершено")