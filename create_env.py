#!/usr/bin/env python3
"""
Скрипт для создания файла .env
"""

import os

def create_env_file():
    """Создает файл .env с базовыми настройками"""
    
    env_content = """# Telegram Bot Token (получите у @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# ID администратора (ваш Telegram ID - получите у @userinfobot)
SLOVLI_ADMIN_USER_ID=123456789

# Файлы словарей
SLOVLI_WORDS_FILE=words.txt

# База данных
SLOVLI_DB_FILE=slovli.db

# Кодировка файлов словарей (опционально)
SLOVLI_WORDS_ENCODING=utf-8
"""
    
    if os.path.exists('.env'):
        print("⚠️  Файл .env уже существует!")
        response = input("Перезаписать? (y/N): ")
        if response.lower() != 'y':
            print("Отменено.")
            return
    
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("✅ Файл .env создан!")
    print("\n📝 Что нужно сделать:")
    print("1. Получите токен бота у @BotFather")
    print("2. Получите ваш ID у @userinfobot")
    print("3. Отредактируйте файл .env и замените значения")
    print("4. Перезапустите бота")

if __name__ == "__main__":
    create_env_file()
