#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Словли — Wordle-подобная игра для Telegram.
Режим: ОДНА игра на чат (в личке — персональная), статистика на пользователя.

Зависимости:
    python-telegram-bot==21.6

Переменные окружения:
    TELEGRAM_BOT_TOKEN   — токен бота от BotFather (обязательно)
    SLOVLI_WORDS_FILE    — путь к словарю (по умолчанию words.txt)
    SLOVLI_DB_FILE       — путь к SQLite (по умолчанию slovli.db)
    SLOVLI_WORDS_ENCODING — необязательная явная кодировка словаря (например cp1251)

Формат words.txt:
    По одному слову в строке, UTF-8 желательно.
    Скрипт сам нормализует: верхний регистр, Ё→Е, только А-Я.
"""

import json
import os
import random
import re
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
)

# ===========================
# Конфигурация
# ===========================
ATTEMPTS = 6
WORD_LEN = 5
WORDS_FILE = os.getenv("SLOVLI_WORDS_FILE", "words.txt")
DB_FILE = os.getenv("SLOVLI_DB_FILE", "slovli.db")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# ===========================
# Утилиты
# ===========================
def normalize_word(w: str) -> str:
    """К верхнему регистру, Ё→Е, только кириллица."""
    w = w.strip().upper()
    w = w.replace("Ё", "Е")
    w = re.sub(r"[^А-Я]", "", w)
    return w

def load_words(path: str, length: int) -> List[str]:
    """
    Загружает словарь из любого формата:
    - берём весь файл целиком,
    - приводим к ВЕРХНЕМУ РЕГИСТРУ и Ё->Е,
    - извлекаем ТОЛЬКО отдельные слова ровно из length букв,
      с учётом границ (не первые буквы более длинного слова).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Не найден файл словаря: {path}")

    encodings: List[str] = []
    env_enc = os.getenv("SLOVLI_WORDS_ENCODING")
    if env_enc:
        encodings.append(env_enc)
    encodings += ["utf-8", "utf-8-sig", "cp1251", "koi8-r", "mac_cyrillic"]

    last_err: Optional[Exception] = None
    tried: List[str] = []

    # Регекc: строго 5 (length) кириллических букв, с границами слова
    # (?<![А-Я])   — перед словом НЕ буква (левая граница)
    # (?![А-Я])    — после слова НЕ буква (правая граница)
    def extract_words(text: str) -> List[str]:
        text = text.upper().replace("Ё", "Е")
        tokens = re.findall(rf"(?<![А-Я])[А-Я]{{{length}}}(?![А-Я])", text)
        # уберём дубликаты, отсортируем
        return sorted(set(tokens))

    for enc in encodings:
        try:
            text = p.read_text(encoding=enc, errors="strict")
            words = extract_words(text)
            if len(words) < 1000:
                raise ValueError(f"Слов мало: {len(words)}. Пополните {path}.")
            return words
        except Exception as e:
            tried.append(enc)
            last_err = e

    raise RuntimeError(
        f"Не удалось прочитать {path} (пробовал: {', '.join(tried)}). "
        f"Последняя ошибка: {last_err}"
    )

def score_guess(guess: str, answer: str) -> Tuple[str, List[str]]:
    """
    Оценка попытки с учётом повторяющихся букв.
    Возвращает: строка-эмодзи и список статусов ['correct'|'present'|'absent'].
    """
    n = len(answer)
    marks = ["absent"] * n
    freq: Dict[str, int] = {}
    for ch in answer:
        freq[ch] = freq.get(ch, 0) + 1

    # Сначала точные совпадения
    for i in range(n):
        if guess[i] == answer[i]:
            marks[i] = "correct"
            freq[guess[i]] -= 1

    # Затем «есть, но не там» / «нет»
    for i in range(n):
        if marks[i] == "correct":
            continue
        ch = guess[i]
        if freq.get(ch, 0) > 0:
            marks[i] = "present"
            freq[ch] -= 1
        else:
            marks[i] = "absent"

    emoji_map = {"correct": "🟩", "present": "🟨", "absent": "⬛"}
    emoji_line = "".join(emoji_map[m] for m in marks)
    return emoji_line, marks

def letters_aggregate(attempts: List[Tuple[str, List[str]]]) -> Dict[str, str]:
    """Лучшая известная оценка по буквам (для мини-клавиатуры). correct > present > absent."""
    best: Dict[str, str] = {}
    rank = {"correct": 3, "present": 2, "absent": 1}
    for guess, marks in attempts:
        for ch, m in zip(guess, marks):
            if ch not in best or rank[m] > rank[best[ch]]:
                best[ch] = m
    return best

def keyboard_line(letter_status: Dict[str, str]) -> str:
    if not letter_status:
        return ""
    order = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    em = {"correct": "🟩", "present": "🟨", "absent": "⬛"}
    blocks = []
    for ch in order:
        st = letter_status.get(ch)
        if st:
            blocks.append(em[st] + ch)
        else:
            blocks.append("▫️" + ch)
    lines = [
        "".join(blocks[0:11]),
        "".join(blocks[11:22]),
        "".join(blocks[22:])
    ]
    return "\n" + "\n".join(lines)

def display_name(update: Update) -> str:
    u = update.effective_user
    return (u.first_name or u.username or "Игрок")

def key_chat_id(update: Update) -> int:
    """Ключ партии — chat_id (в личке это и будет персональной партией)."""
    return update.effective_chat.id

# ===========================
# Хранилище (SQLite)
# ===========================
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    con = db()
    cur = con.cursor()

    # Таблица игр: одна запись на чат
    cur.execute("""
    CREATE TABLE IF NOT EXISTS games (
        chat_id INTEGER PRIMARY KEY,
        answer TEXT NOT NULL,
        attempts_json TEXT NOT NULL DEFAULT '[]',  -- элементы: [guess:str, marks:list[str], user_id:int]
        status TEXT NOT NULL CHECK(status IN ('IN_PROGRESS','WON','LOST')),
        created_at INTEGER NOT NULL
    );
    """)

    # Таблица статистики по пользователю
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stats (
        user_id INTEGER PRIMARY KEY,
        played INTEGER NOT NULL DEFAULT 0,
        wins INTEGER NOT NULL DEFAULT 0,
        current_streak INTEGER NOT NULL DEFAULT 0,
        max_streak INTEGER NOT NULL DEFAULT 0,
        dist1 INTEGER NOT NULL DEFAULT 0,
        dist2 INTEGER NOT NULL DEFAULT 0,
        dist3 INTEGER NOT NULL DEFAULT 0,
        dist4 INTEGER NOT NULL DEFAULT 0,
        dist5 INTEGER NOT NULL DEFAULT 0,
        dist6 INTEGER NOT NULL DEFAULT 0
    );
    """)

    con.commit()
    con.close()

def get_game(chat_id: int) -> Optional[sqlite3.Row]:
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM games WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    con.close()
    return row

def save_game(chat_id: int, answer: str, attempts: List[List], status: str):
    con = db()
    cur = con.cursor()
    cur.execute("""
    INSERT INTO games(chat_id, answer, attempts_json, status, created_at)
    VALUES(?,?,?,?,?)
    ON CONFLICT(chat_id) DO UPDATE SET
        answer=excluded.answer,
        attempts_json=excluded.attempts_json,
        status=excluded.status,
        created_at=excluded.created_at
    """, (chat_id, answer, json.dumps(attempts, ensure_ascii=False), status, int(time.time())))
    con.commit()
    con.close()

def clear_game(chat_id: int):
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM games WHERE chat_id=?", (chat_id,))
    con.commit()
    con.close()

def finish_game_and_update_stats(winner_user_id: Optional[int], won: bool, attempts_count: Optional[int]):
    """
    Завершение партии (удаление из games выполните отдельно),
    обновление личной статистики победителя (если он есть).
    """
    if winner_user_id is None:
        return
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM stats WHERE user_id=?", (winner_user_id,))
    st = cur.fetchone()
    if st is None:
        cur.execute("INSERT INTO stats(user_id) VALUES(?)", (winner_user_id,))
        cur.execute("SELECT * FROM stats WHERE user_id=?", (winner_user_id,))
        st = cur.fetchone()

    played = st["played"] + 1
    wins = st["wins"] + (1 if won else 0)
    current_streak = (st["current_streak"] + 1) if won else 0
    max_streak = max(st["max_streak"], current_streak)

    dist = [st[f"dist{i}"] for i in range(1, 7)]
    if won and attempts_count and 1 <= attempts_count <= 6:
        dist[attempts_count - 1] += 1

    cur.execute("""
    UPDATE stats SET played=?, wins=?, current_streak=?, max_streak=?,
        dist1=?,dist2=?,dist3=?,dist4=?,dist5=?,dist6=?
    WHERE user_id=?
    """, (played, wins, current_streak, max_streak, *dist, winner_user_id))
    con.commit()
    con.close()

def get_stats(user_id: int) -> Optional[sqlite3.Row]:
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM stats WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row

# ===========================
# Глобальные данные
# ===========================
WORDS: List[str] = []

def pick_answer() -> str:
    # На всякий случай гарантируем длину.
    while True:
        w = random.choice(WORDS)
        if len(w) == WORD_LEN and re.fullmatch(r"[А-Я]{"+str(WORD_LEN)+"}", w):
            return w

# ===========================
# Хендлеры
# ===========================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Это «Словли» — угадай русское слово из "
        f"{WORD_LEN} букв за {ATTEMPTS} попыток.\n"
        "Одна игра на чат — все участники бросают слова.\n"
        "Команды: /new, /giveup, /stats, /help"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Правила:\n"
        "• 🟩 — буква на своём месте\n"
        "• 🟨 — буква есть, но не на месте\n"
        "• ⬛ — буквы нет в слове\n\n"
        "Пиши слова кириллицей, ровно 5 букв. /new — новая игра, /giveup — сдаться, /stats — твоя статистика."
    )

async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = key_chat_id(update)
    g = get_game(chat_id)
    if g and g["status"] == "IN_PROGRESS":
        # Завершаем старую как проигрыш для чата (без изменения личной статистики)
        clear_game(chat_id)
        await update.message.reply_text(f"Предыдущая игра завершена. Ответ был: {g['answer']}")

    answer = pick_answer()
    print(f"[DEBUG] Загадано слово для чата {chat_id}: {answer}")  # <-- вот это лог
    save_game(chat_id, answer, [], "IN_PROGRESS")
    await update.message.reply_text(
        f"Поехали! Загадано слово из {WORD_LEN} букв. У вас {ATTEMPTS} попыток."
    )

async def cmd_giveup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = key_chat_id(update)
    g = get_game(chat_id)
    if not g or g["status"] != "IN_PROGRESS":
        await update.message.reply_text("Сейчас нет активной игры. Нажми /new чтобы начать.")
        return
    answer = g["answer"]
    clear_game(chat_id)
    await update.message.reply_text(f"Сдаёмся. Ответ был: {answer}\nНовая игра: /new")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    st = get_stats(user_id)
    if not st or st["played"] == 0:
        await update.message.reply_text("Статистика пока пуста. Сыграй /new!")
        return
    played = st["played"]
    wins = st["wins"]
    winrate = round(100 * wins / played)
    cs = st["current_streak"]
    ms = st["max_streak"]
    bars = []
    for i in range(1, 7):
        val = st[f"dist{i}"]
        bars.append(f"{i}: {'▇' * min(val, 20)} {val}")
    dist_text = "\n".join(bars)
    await update.message.reply_text(
        f"Сыграно: {played}\nПобед: {wins} ({winrate}%)\n"
        f"Серия: {cs}\nМакс. серия: {ms}\n\nРаспределение попыток:\n{dist_text}"
    )

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    chat_id = key_chat_id(update)
    user_id = update.effective_user.id
    name = display_name(update)

    g = get_game(chat_id)
    if not g or g["status"] != "IN_PROGRESS":
        await update.message.reply_text("Нет активной игры. Жми /new чтобы начать.")
        return

    guess_raw = msg
    guess = normalize_word(guess_raw)

    # Валидация
    if len(guess) != WORD_LEN:
        await update.message.reply_text(f"Нужно слово из {WORD_LEN} букв.")
        return
    if not re.fullmatch(r"[А-Я]{"+str(WORD_LEN)+"}", guess):
        await update.message.reply_text("Только русские буквы, без пробелов и символов.")
        return
    if guess not in WORDS:
        await update.message.reply_text("Такого слова нет в словаре.")
        return

    answer = g["answer"]
    attempts = json.loads(g["attempts_json"])  # список элементов [guess, marks, user_id]
    emoji_line, marks = score_guess(guess, answer)
    attempts.append([guess, marks, user_id])

    # Проверим результаты
    if guess == answer:
        # Победа: засчитываем победителю личную статистику
        finish_game_and_update_stats(user_id, True, len(attempts))
        # Чистим игру чата
        clear_game(chat_id)
        kb = letters_aggregate([(a[0], a[1]) for a in attempts])
        await update.message.reply_text(
            f"{emoji_line}\n{guess} — {name}\n\nПобеда за {len(attempts)} попыток! 🎉{keyboard_line(kb)}\n"
            "Новая игра: /new"
        )
        return

    # Если ещё не угадали — продолжаем
    if len(attempts) >= ATTEMPTS:
        # Поражение чата (без личной победы)
        clear_game(chat_id)
        await update.message.reply_text(
            f"{emoji_line}\n{guess} — {name}\n\nНе вышло. Ответ был: {answer}\nПопробуем ещё? /new"
        )
        return

    # Сохраняем прогресс (IN_PROGRESS)
    save_game(chat_id, answer, attempts, "IN_PROGRESS")
    kb = letters_aggregate([(a[0], a[1]) for a in attempts])
    left = ATTEMPTS - len(attempts)
    await update.message.reply_text(
        f"{emoji_line}\n{guess} — {name}\nОсталось попыток: {left}{keyboard_line(kb)}"
    )

# ===========================
# Точка входа (sync)
# ===========================
def main():
    global WORDS
    init_db()
    WORDS = load_words(WORDS_FILE, WORD_LEN)
    if not TOKEN:
        raise RuntimeError("Нужно задать переменную окружения TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("giveup", cmd_giveup))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print(f"Загружено слов: {len(WORDS)}. Бот запущен.")
    app.run_polling()

if __name__ == "__main__":
    main()
