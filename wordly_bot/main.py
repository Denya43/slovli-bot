from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import TOKEN
from .db import init_db
from .handlers import (
    bootstrap_words,
    cmd_giveup,
    cmd_help,
    cmd_new,
    cmd_start,
    cmd_stats,
    on_text,
    set_word_lists,
)


def main():
    init_db()
    words_all, answer_pool = bootstrap_words()
    set_word_lists(words_all, answer_pool)

    if not TOKEN:
        raise RuntimeError("Нужен TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("giveup", cmd_giveup))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("Бот запущен.")
    app.run_polling()


if __name__ == "__main__":
    main()



