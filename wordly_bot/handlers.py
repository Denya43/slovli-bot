import json
import re
from typing import List, Tuple

from telegram import Update
from telegram.ext import ContextTypes

from .config import ATTEMPTS, WORD_LEN, TOKEN, WORDS_FILE, ADMIN_USER_ID
from .db import (
    clear_game,
    finish_game_and_update_stats,
    get_chat_leaderboard,
    get_chat_stats,
    get_game,
    get_stats,
    init_db,
    record_chat_win,
    save_game,
    update_chat_stats,
    get_chat_settings,
    save_chat_settings,
    get_custom_words,
    add_custom_word,
    remove_custom_word,
)
from .game import (
    letters_aggregate,
    load_words,
    normalize_word,
    pick_answer,
    score_guess,
    get_words_for_length,
)
from .render import reply_with_grid_image


WORDS_ALL: List[str] = []
ANSWER_POOL: List[str] = []
WORDS_BY_LENGTH: dict = {}
ANSWER_POOLS_BY_LENGTH: dict = {}

def set_word_lists(words_all: List[str], answer_pool: List[str]) -> None:
    global WORDS_ALL, ANSWER_POOL
    WORDS_ALL = words_all
    ANSWER_POOL = answer_pool

def set_words_by_length(words_by_length: dict, answer_pools_by_length: dict) -> None:
    global WORDS_BY_LENGTH, ANSWER_POOLS_BY_LENGTH
    WORDS_BY_LENGTH = words_by_length
    ANSWER_POOLS_BY_LENGTH = answer_pools_by_length


def display_name(update: Update) -> str:
    u = update.effective_user
    return (u.first_name or u.username or "Игрок")


def key_chat_id(update: Update) -> int:
    return update.effective_chat.id


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = key_chat_id(update)
    settings = get_chat_settings(chat_id)
    word_length = settings["word_length"] if settings else 5
    
    await update.message.reply_text(
        f"Привет! Это «Словли» — угадай слово из {word_length} букв за {ATTEMPTS} попыток.\n"
        "Одна игра на чат. Команды: /new, /giveup, /stats, /help"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = key_chat_id(update)
    settings = get_chat_settings(chat_id)
    word_length = settings["word_length"] if settings else 5
    
    help_text = (
        "Правила:\n"
        "🟩 — буква на своём месте\n"
        "🟨 — буква есть, но не на месте\n"
        "⬛ — буквы нет в слове\n\n"
        f"Пиши слова кириллицей, ровно {word_length} букв.\n\n"
        "Команды:\n"
        "/new — новая игра\n"
        "/giveup — сдаться\n"
        "/stats — статистика\n"
        "/length [число] — установить длину слова (4-9)\n"
        "/checkword [слово] — проверить слово в словаре\n"
        "/help — эта справка"
    )
    
    # Добавляем административные команды только для админов
    if update.effective_user.id == ADMIN_USER_ID:
        help_text += "\n\nАдмин команды:\n"
        help_text += "/addword <слово> — добавить слово\n"
        help_text += "/removeword <слово> — удалить слово\n"
        help_text += "/words [длина] — статистика слов"
    
    await update.message.reply_text(help_text)


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = key_chat_id(update)
    g = get_game(chat_id)
    if g and g["status"] == "IN_PROGRESS":
        clear_game(chat_id)
        await update.message.reply_text(f"Предыдущая игра завершена. Ответ был: {g['answer']}")

    # Получаем настройки чата
    settings = get_chat_settings(chat_id)
    word_length = settings["word_length"] if settings else 5
    
    try:
        # Получаем пул слов для данной длины
        pool = ANSWER_POOLS_BY_LENGTH.get(word_length, [])
        if not pool:
            await update.message.reply_text(f"Нет слов длиной {word_length} букв в словаре.")
            return
        
        # Добавляем пользовательские слова
        custom_words = get_custom_words(word_length)
        pool = pool + custom_words
        
        if not pool:
            await update.message.reply_text(f"Нет слов длиной {word_length} букв в словаре.")
            return
        
        answer = pick_answer(pool, word_length)
        print(f"[DEBUG] Загадано для чата {chat_id}: {answer} (длина: {word_length})")
        save_game(chat_id, answer, [], "IN_PROGRESS", word_length)
        await update.message.reply_text(
            f"Поехали! Загадано слово из {word_length} букв. У вас {ATTEMPTS} попыток."
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def cmd_giveup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = key_chat_id(update)
    g = get_game(chat_id)
    if not g or g["status"] != "IN_PROGRESS":
        await update.message.reply_text("Сейчас нет игры. /new — начать.")
        return
    answer = g["answer"]
    clear_game(chat_id)
    await update.message.reply_text(f"Сдаёмся. Ответ был: {answer}\n/new — новая игра")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    st = get_stats(user_id)
    if not st or st["played"] == 0:
        await update.message.reply_text("Статистика пуста. Сыграй /new!")
        return
    winrate = round(100 * st["wins"] / st["played"])
    await update.message.reply_text(
        f"Сыграно: {st['played']}\n"
        f"Побед: {st['wins']} ({winrate}%)\n"
        f"Серия: {st['current_streak']}, рекорд: {st['max_streak']}"
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    chat_id = key_chat_id(update)
    user_id = update.effective_user.id
    name = display_name(update)

    g = get_game(chat_id)
    if not g or g["status"] != "IN_PROGRESS":
        return

    tokens = re.findall(r"[А-ЯЁа-яё]+", msg)
    if len(tokens) != 1:
        return

    guess = normalize_word(tokens[0])
    
    # Получаем настройки чата для определения длины слова
    settings = get_chat_settings(chat_id)
    word_length = settings["word_length"] if settings else 5
    
    if len(guess) != word_length:
        await update.message.reply_text(f"Нужно слово из {word_length} букв.")
        return
    if not re.fullmatch(r"[А-Я]{" + str(word_length) + "}", guess):
        await update.message.reply_text("Только кириллица, без пробелов и символов.")
        return
    
    # Проверяем слово в словаре для данной длины
    words_for_length = get_words_for_length(word_length, WORDS_BY_LENGTH.get(word_length, []), get_custom_words(word_length))
    if guess not in words_for_length:
        await update.message.reply_text("Такого слова нет в словаре.")
        return

    answer = g["answer"]
    attempts = json.loads(g["attempts_json"])  # список: [guess, marks, user_id]

    # Запретим повторные попытки тем же словом в рамках одной игры (до добавления нового хода)
    previous_guesses = {a[0] for a in attempts}
    if guess in previous_guesses:
        await update.message.reply_text("Это слово уже пробовали в этой игре.")
        return

    marks = score_guess(guess, answer)
    attempts.append([guess, marks, user_id])

    if guess == answer:
        finish_game_and_update_stats(user_id, True, len(attempts))
        update_chat_stats(chat_id, True, len(attempts))
        record_chat_win(chat_id, user_id, name)
        clear_game(chat_id)
        await reply_with_grid_image(update, [(a[0], a[1]) for a in attempts], word_length)
        st = get_chat_stats(chat_id)
        if st and st["played"]:
            winrate = round(100 * st["wins"] / st["played"])
            leaderboard = get_chat_leaderboard(chat_id, limit=10)
            lb_text = "\n".join(
                f"{i+1}. {row['name'] or row['user_id']}: {row['wins']}"
                for i, row in enumerate(leaderboard)
            ) or "нет победителей"
            await update.message.reply_text(
                f"{guess} — {name}\nПобеда за {len(attempts)} попыток! 🎉\n\n"
                f"Сыграно в чате: {st['played']}\n"
                f"Побед чата: {st['wins']} ({winrate}%)\n"
                f"Серия: {st['current_streak']}, рекорд: {st['max_streak']}\n\n"
                f"Топ победителей:\n{lb_text}\n/new"
            )
        else:
            leaderboard = get_chat_leaderboard(chat_id, limit=10)
            lb_text = "\n".join(
                f"{i+1}. {row['name'] or row['user_id']}: {row['wins']}"
                for i, row in enumerate(leaderboard)
            ) or "нет победителей"
            await update.message.reply_text(
                f"{guess} — {name}\nПобеда за {len(attempts)} попыток! 🎉\n\n"
                f"Топ победителей:\n{lb_text}\n/new"
            )
        return

    if len(attempts) >= ATTEMPTS:
        update_chat_stats(chat_id, False, None)
        clear_game(chat_id)
        await reply_with_grid_image(update, [(a[0], a[1]) for a in attempts], word_length)
        st = get_chat_stats(chat_id)
        if st and st["played"]:
            winrate = round(100 * st["wins"] / st["played"])
            await update.message.reply_text(
                f"{guess} — {name}\nНе вышло. Ответ был: {answer}\n\n"
                f"Сыграно в чате: {st['played']}\n"
                f"Побед чата: {st['wins']} ({winrate}%)\n"
                f"Серия: {st['current_streak']}, рекорд: {st['max_streak']}\n/new"
            )
        else:
            await update.message.reply_text(
                f"{guess} — {name}\nНе вышло. Ответ был: {answer}\n/new"
            )
        return

    save_game(chat_id, answer, attempts, "IN_PROGRESS")
    left = ATTEMPTS - len(attempts)
    await reply_with_grid_image(update, [(a[0], a[1]) for a in attempts], word_length)
    await update.message.reply_text(
        f"{guess} — {name}\nОсталось попыток: {left}"
    )


def bootstrap_words() -> Tuple[List[str], List[str]]:
    all_words = load_words(WORDS_FILE, WORD_LEN, min_count=1000)
    pool = load_words(WORDS_FILE, WORD_LEN, min_count=1)
    inter = sorted(set(pool) & set(all_words))
    if not inter:
        raise RuntimeError("ANSWER_POOL не пересекается с WORDS_ALL")
    return all_words, inter


async def cmd_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить длину слова для чата"""
    chat_id = key_chat_id(update)
    
    if not context.args:
        # Показать текущую длину
        settings = get_chat_settings(chat_id)
        current_length = settings["word_length"] if settings else 5
        await update.message.reply_text(
            f"Текущая длина слова: {current_length} букв\n"
            f"Используйте /length <число> для изменения (4-9 букв)"
        )
        return
    
    try:
        length = int(context.args[0])
        if length < 4 or length > 9:
            await update.message.reply_text("Длина слова должна быть от 4 до 9 букв.")
            return
        
        # Проверяем, есть ли слова такой длины
        if length not in WORDS_BY_LENGTH or not WORDS_BY_LENGTH[length]:
            await update.message.reply_text(f"Нет слов длиной {length} букв в словаре.")
            return
        
        save_chat_settings(chat_id, length)
        await update.message.reply_text(f"Длина слова установлена: {length} букв")
        
    except ValueError:
        await update.message.reply_text("Укажите число от 4 до 9.")


async def cmd_addword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить слово в пользовательский словарь"""
    # Debug: выводим ID пользователя и администратора
    user_id = update.effective_user.id
    print(f"[DEBUG] Пользователь ID: {user_id}, Админ ID: {ADMIN_USER_ID}")
    
    # Проверяем права администратора
    if ADMIN_USER_ID == 0:
        await update.message.reply_text(
            "❌ Администратор не настроен!\n\n"
            "Создайте файл .env в корне проекта и добавьте:\n"
            "SLOVLI_ADMIN_USER_ID=ваш_id\n\n"
            "Чтобы получить ваш ID, напишите боту @userinfobot"
        )
        return
    
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text(
            f"❌ Эта команда доступна только администратору!\n\n"
            f"Ваш ID: {user_id}\n"
            f"Админ ID: {ADMIN_USER_ID}\n\n"
            "Если вы администратор, проверьте настройки в файле .env"
        )
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /addword <слово>")
        return
    
    # Объединяем все аргументы в одно слово
    word_input = " ".join(context.args)
    word = normalize_word(word_input)
    
    if len(word) < 4 or len(word) > 9:
        await update.message.reply_text("Длина слова должна быть от 4 до 9 букв.")
        return
    
    if not re.fullmatch(r"[А-Я]{"+str(len(word))+"}", word):
        await update.message.reply_text("Слово должно содержать только кириллические буквы.")
        return
    
    length = len(word)
    
    # Проверяем, где уже есть слово
    base_words = WORDS_BY_LENGTH.get(length, [])
    custom_words = get_custom_words(length)
    
    in_base = word in base_words
    in_custom = word in custom_words
    
    if add_custom_word(word, length, update.effective_user.id):
        await update.message.reply_text(f"✅ Слово '{word}' добавлено в пользовательский словарь ({length} букв)")
    else:
        if in_custom:
            await update.message.reply_text(f"❌ Слово '{word}' уже есть в пользовательском словаре")
        elif in_base:
            await update.message.reply_text(f"❌ Слово '{word}' уже есть в базовом словаре")
        else:
            await update.message.reply_text(f"❌ Слово '{word}' уже есть в словаре (неизвестно где)")


async def cmd_removeword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить слово из пользовательского словаря"""
    # Проверяем права администратора
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Эта команда доступна только администратору.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /removeword <слово>")
        return
    
    # Объединяем все аргументы в одно слово
    word_input = " ".join(context.args)
    word = normalize_word(word_input)
    
    if len(word) < 4 or len(word) > 9:
        await update.message.reply_text("Длина слова должна быть от 4 до 9 букв.")
        return
    
    if not re.fullmatch(r"[А-Я]{"+str(len(word))+"}", word):
        await update.message.reply_text("Слово должно содержать только кириллические буквы.")
        return
    
    length = len(word)
    
    # Проверяем, где находится слово
    base_words = WORDS_BY_LENGTH.get(length, [])
    custom_words = get_custom_words(length)
    
    in_base = word in base_words
    in_custom = word in custom_words
    
    if in_base and not in_custom:
        await update.message.reply_text(
            f"❌ Слово '{word}' находится в базовом словаре, а не в пользовательских словах.\n"
            f"Удалить можно только слова, добавленные через /addword"
        )
        return
    
    if remove_custom_word(word, length):
        await update.message.reply_text(f"✅ Слово '{word}' удалено из пользовательского словаря")
    else:
        await update.message.reply_text(
            f"❌ Слово '{word}' не найдено в пользовательском словаре\n\n"
            f"Проверка:\n"
            f"• В базовом словаре: {'✅' if in_base else '❌'}\n"
            f"• В пользовательских словах: {'✅' if in_custom else '❌'}\n"
            f"• Всего пользовательских слов длиной {length}: {len(custom_words)}"
        )


async def cmd_checkword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить, есть ли слово в словаре"""
    if not context.args:
        await update.message.reply_text("Использование: /checkword <слово>")
        return
    
    # Объединяем все аргументы в одно слово
    word_input = " ".join(context.args)
    word = normalize_word(word_input)
    
    if len(word) < 4 or len(word) > 9:
        await update.message.reply_text("Длина слова должна быть от 4 до 9 букв.")
        return
    
    if not re.fullmatch(r"[А-Я]{"+str(len(word))+"}", word):
        await update.message.reply_text("Слово должно содержать только кириллические буквы.")
        return
    
    length = len(word)
    
    # Проверяем в базовых словах
    base_words = WORDS_BY_LENGTH.get(length, [])
    in_base = word in base_words
    
    # Проверяем в пользовательских словах
    custom_words = get_custom_words(length)
    in_custom = word in custom_words
    
    if in_base and in_custom:
        await update.message.reply_text(f"✅ Слово '{word}' есть в базовом словаре И в пользовательских словах")
    elif in_base:
        await update.message.reply_text(f"✅ Слово '{word}' есть в базовом словаре")
    elif in_custom:
        await update.message.reply_text(f"✅ Слово '{word}' есть в пользовательских словах")
    else:
        await update.message.reply_text(f"❌ Слово '{word}' НЕТ в словаре")


async def cmd_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику слов"""
    # Проверяем права администратора
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Эта команда доступна только администратору.")
        return
    
    if not context.args:
        # Показать общую статистику
        stats = []
        for length in range(4, 10):
            base_words = len(WORDS_BY_LENGTH.get(length, []))
            custom_words = len(get_custom_words(length))
            if base_words > 0 or custom_words > 0:
                stats.append(f"{length} букв: {base_words} базовых + {custom_words} пользовательских")
        
        await update.message.reply_text("Статистика слов:\n" + "\n".join(stats))
        return
    
    try:
        length = int(context.args[0])
        if length < 4 or length > 9:
            await update.message.reply_text("Длина слова должна быть от 4 до 9 букв.")
            return
        
        base_words = len(WORDS_BY_LENGTH.get(length, []))
        custom_words = get_custom_words(length)
        
        msg = f"Слова длиной {length} букв:\n"
        msg += f"Базовых слов: {base_words}\n"
        msg += f"Пользовательских слов: {len(custom_words)}"
        
        if custom_words:
            msg += f"\n\nПользовательские слова:\n{', '.join(custom_words[:20])}"
            if len(custom_words) > 20:
                msg += f"\n... и еще {len(custom_words) - 20}"
        
        await update.message.reply_text(msg)
        
    except ValueError:
        await update.message.reply_text("Укажите корректную длину слова.")



