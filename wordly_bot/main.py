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
    set_words_by_length,
    cmd_length,
    cmd_addword,
    cmd_removeword,
    cmd_words,
    cmd_checkword,
    cmd_addmoderator,
    cmd_removemoderator,
    cmd_moderators,
    cmd_myrole,
)


def main():
    init_db()
    
    # Загружаем слова для всех длин от 4 до 9
    words_by_length = {}
    answer_pools_by_length = {}
    
    for length in range(4, 10):
        try:
            from .game import load_words
            from .config import WORDS_FILE
            words = load_words(WORDS_FILE, length, min_count=100)
            words_by_length[length] = words
            print(f"Загружено {len(words)} слов длиной {length}")
        except Exception as e:
            print(f"Ошибка загрузки слов длиной {length}: {e}")
            words_by_length[length] = []
    
    # Создаем пулы ответов для каждой длины
    for length in range(4, 10):
        if length in words_by_length and words_by_length[length]:
            answer_pools_by_length[length] = words_by_length[length]
        else:
            answer_pools_by_length[length] = []
    
    # Для обратной совместимости
    words_all, answer_pool = bootstrap_words()
    set_word_lists(words_all, answer_pool)
    set_words_by_length(words_by_length, answer_pools_by_length)

    if not TOKEN:
        raise RuntimeError("Нужен TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("giveup", cmd_giveup))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("length", cmd_length))
    app.add_handler(CommandHandler("addword", cmd_addword))
    app.add_handler(CommandHandler("removeword", cmd_removeword))
    app.add_handler(CommandHandler("words", cmd_words))
    app.add_handler(CommandHandler("checkword", cmd_checkword))
    app.add_handler(CommandHandler("addmoderator", cmd_addmoderator))
    app.add_handler(CommandHandler("removemoderator", cmd_removemoderator))
    app.add_handler(CommandHandler("moderators", cmd_moderators))
    app.add_handler(CommandHandler("myrole", cmd_myrole))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    total_words = sum(len(words) for words in words_by_length.values())
    total_pools = sum(len(pool) for pool in answer_pools_by_length.values())
    print(f"Загружено слов: {total_words}; пулов загадок: {total_pools}. Бот запущен.")
    print(f"Доступные длины: {list(words_by_length.keys())}")
    app.run_polling()


if __name__ == "__main__":
    main()



