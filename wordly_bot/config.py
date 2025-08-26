import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Core game config
ATTEMPTS = 6
WORD_LEN = 5

# Files and DB
WORDS_FILE = os.getenv("SLOVLI_WORDS_FILE", "words.txt")
DB_FILE = os.getenv("SLOVLI_DB_FILE", "slovli.db")

# Telegram
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# ID администратора
admin_id_str = os.getenv("SLOVLI_ADMIN_USER_ID")
if admin_id_str is None or admin_id_str == "0":
    print("[WARNING] SLOVLI_ADMIN_USER_ID не установлен! Административные команды недоступны.")
    print("[INFO] Создайте файл .env и добавьте: SLOVLI_ADMIN_USER_ID=ваш_id")
    ADMIN_USER_ID = 0
else:
    try:
        ADMIN_USER_ID = int(admin_id_str)
        print(f"[INFO] Администратор установлен: {ADMIN_USER_ID}")
    except ValueError:
        print(f"[ERROR] Неверный формат SLOVLI_ADMIN_USER_ID: {admin_id_str}")
        print("[INFO] ID должен быть числом (например: 123456789)")
        ADMIN_USER_ID = 0



