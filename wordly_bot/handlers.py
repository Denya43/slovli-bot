import json
import re
from typing import List, Tuple

from telegram import Update
from telegram.ext import ContextTypes

from .config import ATTEMPTS, WORD_LEN, TOKEN, WORDS_FILE, POOL_FILE
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
)
from .game import (
    letters_aggregate,
    load_words,
    normalize_word,
    pick_answer,
    score_guess,
)
from .render import reply_with_grid_image


WORDS_ALL: List[str] = []
ANSWER_POOL: List[str] = []


def display_name(update: Update) -> str:
    u = update.effective_user
    return (u.first_name or u.username or "Игрок")


def key_chat_id(update: Update) -> int:
    return update.effective_chat.id


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Привет! Это «Словли» — угадай слово из {WORD_LEN} букв за {ATTEMPTS} попыток.\n"
        "Одна игра на чат. Команды: /new, /giveup, /stats, /help"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Правила:\n"
        "🟩 — буква на своём месте\n"
        "🟨 — буква есть, но не на месте\n"
        "⬛ — буквы нет в слове\n\n"
        "Пиши слова кириллицей, ровно 5 букв."
    )


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = key_chat_id(update)
    g = get_game(chat_id)
    if g and g["status"] == "IN_PROGRESS":
        clear_game(chat_id)
        await update.message.reply_text(f"Предыдущая игра завершена. Ответ был: {g['answer']}")

    answer = pick_answer(ANSWER_POOL)
    save_game(chat_id, answer, [], "IN_PROGRESS")
    await update.message.reply_text(
        f"Поехали! Загадано слово из {WORD_LEN} букв. У вас {ATTEMPTS} попыток."
    )


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
    dist_text = "\n".join(
        f"{i}: {'▇' * min(st[f'dist{i}'],20)} {st[f'dist{i}']}" for i in range(1, 7)
    )
    await update.message.reply_text(
        f"Сыграно: {st['played']}\n"
        f"Побед: {st['wins']} ({winrate}%)\n"
        f"Серия: {st['current_streak']}, рекорд: {st['max_streak']}\n\n"
        f"Распределение попыток:\n{dist_text}"
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

    if len(guess) != WORD_LEN:
        await update.message.reply_text(f"Нужно слово из {WORD_LEN} букв.")
        return
    if not re.fullmatch(r"[А-Я]{" + str(WORD_LEN) + "}", guess):
        await update.message.reply_text("Только кириллица, без пробелов и символов.")
        return
    if guess not in WORDS_ALL:
        await update.message.reply_text("Такого слова нет в словаре.")
        return

    answer = g["answer"]
    attempts = json.loads(g["attempts_json"])

    marks = score_guess(guess, answer)
    attempts.append([guess, marks, user_id])

    # Запретим повторные попытки тем же словом в рамках одной игры
    previous_guesses = {a[0] for a in attempts}
    if guess in previous_guesses:
        await update.message.reply_text("Это слово уже пробовали в этой игре.")
        return

    if guess == answer:
        finish_game_and_update_stats(user_id, True, len(attempts))
        update_chat_stats(chat_id, True, len(attempts))
        record_chat_win(chat_id, user_id, name)
        clear_game(chat_id)
        await reply_with_grid_image(update, [(a[0], a[1]) for a in attempts])
        st = get_chat_stats(chat_id)
        if st and st["played"]:
            winrate = round(100 * st["wins"] / st["played"])
            dist_text = "\n".join(
                f"{i}: {'▇' * min(st[f'dist{i}'],20)} {st[f'dist{i}']}" for i in range(1, 7)
            )
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
                f"Распределение попыток:\n{dist_text}\n\n"
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
        await reply_with_grid_image(update, [(a[0], a[1]) for a in attempts])
        st = get_chat_stats(chat_id)
        if st and st["played"]:
            winrate = round(100 * st["wins"] / st["played"])
            dist_text = "\n".join(
                f"{i}: {'▇' * min(st[f'dist{i}'],20)} {st[f'dist{i}']}" for i in range(1, 7)
            )
            await update.message.reply_text(
                f"{guess} — {name}\nНе вышло. Ответ был: {answer}\n\n"
                f"Сыграно в чате: {st['played']}\n"
                f"Побед чата: {st['wins']} ({winrate}%)\n"
                f"Серия: {st['current_streak']}, рекорд: {st['max_streak']}\n\n"
                f"Распределение попыток:\n{dist_text}\n/new"
            )
        else:
            await update.message.reply_text(
                f"{guess} — {name}\nНе вышло. Ответ был: {answer}\n/new"
            )
        return

    save_game(chat_id, answer, attempts, "IN_PROGRESS")
    left = ATTEMPTS - len(attempts)
    await reply_with_grid_image(update, [(a[0], a[1]) for a in attempts])
    await update.message.reply_text(
        f"{guess} — {name}\nОсталось попыток: {left}"
    )


def bootstrap_words() -> Tuple[List[str], List[str]]:
    all_words = load_words(WORDS_FILE, WORD_LEN, min_count=1000)
    pool = load_words(POOL_FILE, WORD_LEN, min_count=1)
    inter = sorted(set(pool) & set(all_words))
    if not inter:
        raise RuntimeError("ANSWER_POOL не пересекается с WORDS_ALL")
    return all_words, inter



