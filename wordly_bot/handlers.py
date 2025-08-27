import json
import re
import time
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
    add_moderator,
    remove_moderator,
    get_moderators,
    is_moderator,
    is_admin_or_moderator,
    save_user_info,
    find_user_by_username,
    get_user_info,
)
from .game import (
    letters_aggregate,
    load_words,
    normalize_word,
    pick_answer,
    score_guess,
    get_words_for_length,
    add_word_to_file,
    remove_word_from_file,
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


async def reload_word_dictionaries() -> None:
    """Перезагрузить словари после изменения файла words.txt"""
    global WORDS_BY_LENGTH, ANSWER_POOLS_BY_LENGTH
    
    # Загружаем слова для всех длин от 4 до 9
    words_by_length = {}
    answer_pools_by_length = {}
    
    for length in range(4, 10):
        try:
            words = load_words(WORDS_FILE, length, min_count=100)
            words_by_length[length] = words
            print(f"Перезагружено {len(words)} слов длиной {length}")
        except Exception as e:
            print(f"Ошибка перезагрузки слов длиной {length}: {e}")
            words_by_length[length] = []
    
    # Создаем пулы ответов для каждой длины
    for length in range(4, 10):
        if length in words_by_length and words_by_length[length]:
            answer_pools_by_length[length] = words_by_length[length]
        else:
            answer_pools_by_length[length] = []
    
    # Обновляем глобальные переменные
    WORDS_BY_LENGTH = words_by_length
    ANSWER_POOLS_BY_LENGTH = answer_pools_by_length


def display_name(update: Update) -> str:
    u = update.effective_user
    return (u.first_name or u.username or "Игрок")


def key_chat_id(update: Update) -> int:
    return update.effective_chat.id


def save_user_from_update(update: Update):
    """Сохранить информацию о пользователе из Update"""
    user = update.effective_user
    if user:
        save_user_info(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )


def check_admin_permissions(user_id: int) -> tuple[bool, str]:
    """Проверить права администратора. Возвращает (разрешено, сообщение_об_ошибке)"""
    if ADMIN_USER_ID == 0:
        return False, (
            "❌ Администратор не настроен!\n\n"
            "Создайте файл .env в корне проекта и добавьте:\n"
            "SLOVLI_ADMIN_USER_ID=ваш_id\n\n"
            "Чтобы получить ваш ID, напишите боту @userinfobot"
        )
    
    if user_id != ADMIN_USER_ID:
        return False, (
            f"❌ Эта команда доступна только администратору!\n\n"
            f"Ваш ID: {user_id}\n"
            f"Админ ID: {ADMIN_USER_ID}\n\n"
            "Если вы администратор, проверьте настройки в файле .env"
        )
    
    return True, ""


def check_moderator_permissions(user_id: int) -> tuple[bool, str]:
    """Проверить права модератора или администратора. Возвращает (разрешено, сообщение_об_ошибке)"""
    if ADMIN_USER_ID == 0:
        return False, (
            "❌ Администратор не настроен!\n\n"
            "Создайте файл .env в корне проекта и добавьте:\n"
            "SLOVLI_ADMIN_USER_ID=ваш_id\n\n"
            "Чтобы получить ваш ID, напишите боту @userinfobot"
        )
    
    if not is_admin_or_moderator(user_id, ADMIN_USER_ID):
        role = "администратор" if user_id == ADMIN_USER_ID else ("модератор" if is_moderator(user_id) else "обычный пользователь")
        return False, (
            f"❌ Эта команда доступна только администратору и модераторам!\n\n"
            f"Ваш ID: {user_id}\n"
            f"Ваша роль: {role}\n\n"
            "Обратитесь к администратору для получения прав модератора."
        )
    
    return True, ""


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сохраняем информацию о пользователе
    save_user_from_update(update)
    
    chat_id = key_chat_id(update)
    settings = get_chat_settings(chat_id)
    word_length = settings["word_length"] if settings else 5
    
    await update.message.reply_text(
        f"Привет! Это «Словли» — угадай слово из {word_length} букв за {ATTEMPTS} попыток.\n"
        "Одна игра на чат. Команды: /new, /giveup, /stats, /help"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сохраняем информацию о пользователе
    save_user_from_update(update)
    
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
    
    user_id = update.effective_user.id
    
    # Добавляем команды для модераторов и администраторов
    if is_admin_or_moderator(user_id, ADMIN_USER_ID):
        help_text += "\n\nКоманды модератора:\n"
        help_text += "/addword <слово> — добавить слово\n"
        help_text += "/removeword <слово> — удалить слово\n"
        help_text += "/words [длина] — статистика слов\n"
        help_text += "/myrole — показать свою роль\n"
    
    # Добавляем команды только для администратора
    if user_id == ADMIN_USER_ID:
        help_text += "\n\nКоманды администратора:\n"
        help_text += "/addmoderator <ID или @username> — добавить модератора\n"
        help_text += "/removemoderator <ID или @username> — удалить модератора\n"
        help_text += "/moderators — список модераторов"
    
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
        
        # Пул уже содержит все слова из файла (включая добавленные через /addword)
        
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
    # Сохраняем информацию о пользователе
    save_user_from_update(update)
    
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
    words_for_length = get_words_for_length(word_length, WORDS_BY_LENGTH.get(word_length, []))
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
    """Добавить слово в словарь"""
    user_id = update.effective_user.id
    
    # Проверяем права модератора или администратора
    allowed, error_message = check_moderator_permissions(user_id)
    if not allowed:
        await update.message.reply_text(error_message)
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
    
    if add_word_to_file(word, WORDS_FILE):
        await update.message.reply_text(f"✅ Слово '{word}' добавлено в словарь ({len(word)} букв)")
        # Перезагружаем словари для всех длин
        await reload_word_dictionaries()
    else:
        await update.message.reply_text(f"❌ Слово '{word}' уже есть в словаре")


async def cmd_removeword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить слово из словаря"""
    user_id = update.effective_user.id
    
    # Проверяем права модератора или администратора
    allowed, error_message = check_moderator_permissions(user_id)
    if not allowed:
        await update.message.reply_text(error_message)
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
    
    if remove_word_from_file(word, WORDS_FILE):
        await update.message.reply_text(f"✅ Слово '{word}' удалено из словаря")
        # Перезагружаем словари для всех длин
        await reload_word_dictionaries()
    else:
        await update.message.reply_text(f"❌ Слово '{word}' не найдено в словаре")


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
    
    # Проверяем в словаре
    words = WORDS_BY_LENGTH.get(length, [])
    in_dictionary = word in words
    
    if in_dictionary:
        await update.message.reply_text(f"✅ Слово '{word}' есть в словаре")
    else:
        await update.message.reply_text(f"❌ Слово '{word}' НЕТ в словаре")


async def cmd_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику слов"""
    user_id = update.effective_user.id
    
    # Проверяем права модератора или администратора
    allowed, error_message = check_moderator_permissions(user_id)
    if not allowed:
        await update.message.reply_text(error_message)
        return
    
    if not context.args:
        # Показать общую статистику
        stats = []
        for length in range(4, 10):
            word_count = len(WORDS_BY_LENGTH.get(length, []))
            if word_count > 0:
                stats.append(f"{length} букв: {word_count} слов")
        
        await update.message.reply_text("Статистика слов:\n" + "\n".join(stats))
        return
    
    try:
        length = int(context.args[0])
        if length < 4 or length > 9:
            await update.message.reply_text("Длина слова должна быть от 4 до 9 букв.")
            return
        
        words = WORDS_BY_LENGTH.get(length, [])
        
        msg = f"Слова длиной {length} букв: {len(words)}"
        
        if words and len(words) <= 50:
            # Показываем все слова если их не много
            msg += f"\n\nВсе слова:\n{', '.join(words[:50])}"
        elif words:
            # Показываем только первые 20
            msg += f"\n\nПервые 20 слов:\n{', '.join(words[:20])}"
            msg += f"\n... и еще {len(words) - 20}"
        
        await update.message.reply_text(msg)
        
    except ValueError:
        await update.message.reply_text("Укажите корректную длину слова.")


async def cmd_addmoderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить модератора (только для администратора)"""
    # Сохраняем информацию о пользователе
    save_user_from_update(update)
    
    user_id = update.effective_user.id
    
    # Проверяем права администратора (только админ может добавлять модераторов)
    allowed, error_message = check_admin_permissions(user_id)
    if not allowed:
        await update.message.reply_text(error_message)
        return
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /addmoderator <user_id или @username>\n\n"
            "Примеры:\n"
            "/addmoderator 123456789\n"
            "/addmoderator @username\n"
            "/addmoderator username\n\n"
            "💡 Чтобы добавить по username, пользователь должен хотя бы раз написать боту"
        )
        return
    
    arg = context.args[0]
    
    # Пробуем определить, что передано - ID или username
    try:
        # Если это число - значит ID
        moderator_id = int(arg)
        user_info = get_user_info(moderator_id)
        username = user_info['username'] if user_info else ""
        
    except ValueError:
        # Если не число - значит username
        username = arg.lstrip('@')  # Убираем @ если есть
        user_info = find_user_by_username(username)
        
        if not user_info:
            await update.message.reply_text(
                f"❌ Пользователь @{username} не найден!\n\n"
                "Возможные причины:\n"
                "• Пользователь никогда не писал боту\n"
                "• Неправильный username\n\n"
                "Попросите пользователя написать любое сообщение боту, затем повторите команду."
            )
            return
            
        moderator_id = user_info['user_id']
        username = user_info['username']
    
    if moderator_id == ADMIN_USER_ID:
        await update.message.reply_text("❌ Администратор не может быть модератором")
        return
    
    if add_moderator(moderator_id, username, user_id):
        display_name = f"@{username}" if username else str(moderator_id)
        await update.message.reply_text(
            f"✅ Пользователь {display_name} (ID: {moderator_id}) добавлен в модераторы"
        )
    else:
        display_name = f"@{username}" if username else str(moderator_id)
        await update.message.reply_text(f"❌ Пользователь {display_name} уже является модератором")


async def cmd_removemoderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить модератора (только для администратора)"""
    # Сохраняем информацию о пользователе
    save_user_from_update(update)
    
    user_id = update.effective_user.id
    
    # Проверяем права администратора (только админ может удалять модераторов)
    allowed, error_message = check_admin_permissions(user_id)
    if not allowed:
        await update.message.reply_text(error_message)
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /removemoderator <user_id или @username>")
        return
    
    arg = context.args[0]
    
    # Пробуем определить, что передано - ID или username
    try:
        # Если это число - значит ID
        moderator_id = int(arg)
        user_info = get_user_info(moderator_id)
        username = user_info['username'] if user_info else ""
        
    except ValueError:
        # Если не число - значит username
        username = arg.lstrip('@')  # Убираем @ если есть
        user_info = find_user_by_username(username)
        
        if not user_info:
            await update.message.reply_text(f"❌ Пользователь @{username} не найден!")
            return
            
        moderator_id = user_info['user_id']
        username = user_info['username']
    
    if remove_moderator(moderator_id):
        display_name = f"@{username}" if username else str(moderator_id)
        await update.message.reply_text(f"✅ Пользователь {display_name} (ID: {moderator_id}) удален из модераторов")
    else:
        display_name = f"@{username}" if username else str(moderator_id)
        await update.message.reply_text(f"❌ Пользователь {display_name} не является модератором")


async def cmd_moderators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список модераторов (только для администратора)"""
    user_id = update.effective_user.id
    
    # Проверяем права администратора (только админ может видеть список модераторов)
    allowed, error_message = check_admin_permissions(user_id)
    if not allowed:
        await update.message.reply_text(error_message)
        return
    
    moderators = get_moderators()
    
    if not moderators:
        await update.message.reply_text("📝 Модераторов пока нет")
        return
    
    msg = "👥 Список модераторов:\n\n"
    for mod in moderators:
        username_part = f" ({mod['username']})" if mod['username'] else ""
        added_at = time.strftime("%Y-%m-%d %H:%M", time.localtime(mod['added_at']))
        msg += f"• {mod['user_id']}{username_part}\n  Добавлен: {added_at}\n\n"
    
    await update.message.reply_text(msg)


async def cmd_myrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать свою роль"""
    user_id = update.effective_user.id
    
    if user_id == ADMIN_USER_ID:
        role = "👑 Администратор"
    elif is_moderator(user_id):
        role = "🛡️ Модератор"
    else:
        role = "👤 Пользователь"
    
    await update.message.reply_text(
        f"Ваш ID: {user_id}\n"
        f"Ваша роль: {role}"
    )



