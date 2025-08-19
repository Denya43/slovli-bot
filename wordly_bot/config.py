import os

# Core game config
ATTEMPTS = 6
WORD_LEN = 5

# Files and DB
WORDS_FILE = os.getenv("SLOVLI_WORDS_FILE", "words.txt")
POOL_FILE = os.getenv("SLOVLI_POOL_FILE", "russian_5letter_nouns_200.txt")
DB_FILE = os.getenv("SLOVLI_DB_FILE", "slovli.db")

# Telegram
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")



