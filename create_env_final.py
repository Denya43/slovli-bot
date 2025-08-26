#!/usr/bin/env python3
"""
Создает файл .env с правильными настройками
"""

env_content = """# Telegram Bot Token (получите у @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# ID администратора (ваш Telegram ID)
SLOVLI_ADMIN_USER_ID=316049311

# Файлы словарей
SLOVLI_WORDS_FILE=words.txt

# База данных
SLOVLI_DB_FILE=slovli.db
"""

with open('.env', 'w', encoding='utf-8') as f:
    f.write(env_content)

print("✅ Файл .env создан с вашим ID: 316049311")
print("\n📝 Теперь нужно:")
print("1. Заменить 'your_bot_token_here' на ваш токен бота")
print("2. Перезапустить бота")
print("3. Попробовать команду /addword 5 ПРИВЕТ")
