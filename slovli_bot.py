#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Словли — Wordle-подобная игра для Telegram.
"""

import json
import os
import random
import re
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from io import BytesIO

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
POOL_FILE = os.getenv("SLOVLI_POOL_FILE", "russian_5letter_nouns_200.txt")  
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

def load_words(path: str, length: int, *, min_count: int = 1000) -> List[str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Не найден файл словаря: {path}")

    encodings = ["utf-8", "utf-8-sig", "cp1251", "koi8-r", "mac_cyrillic"]
    env_enc = os.getenv("SLOVLI_WORDS_ENCODING")
    if env_enc:
        encodings.insert(0, env_enc)

    last_err = None
    tried = []

    def extract_words(text: str) -> List[str]:
        text = text.upper().replace("Ё", "Е")
        tokens = re.findall(rf"(?<![А-Я])[А-Я]{{{length}}}(?![А-Я])", text)
        return sorted(set(tokens))

    for enc in encodings:
        try:
            text = p.read_text(encoding=enc, errors="strict")
            words = extract_words(text)
            if len(words) < min_count:
                raise ValueError(f"Слов мало: {len(words)}. Пополните {path}.")
            return words
        except Exception as e:
            tried.append(enc)
            last_err = e

    raise RuntimeError(f"Не удалось прочитать {path} (пробовал: {', '.join(tried)}). {last_err}")

def score_guess(guess: str, answer: str) -> List[str]:
    """Возвращает список статусов ['correct'|'present'|'absent'] для каждой буквы."""
    n = len(answer)
    marks = ["absent"] * n
    freq: Dict[str, int] = {}
    for ch in answer:
        freq[ch] = freq.get(ch, 0) + 1

    for i in range(n):
        if guess[i] == answer[i]:
            marks[i] = "correct"
            freq[guess[i]] -= 1

    for i in range(n):
        if marks[i] == "correct":
            continue
        ch = guess[i]
        if freq.get(ch, 0) > 0:
            marks[i] = "present"
            freq[ch] -= 1
        else:
            marks[i] = "absent"

    return marks

def format_attempt(guess: str, marks: List[str]) -> str:
    """Формат одной попытки: 🟩Р🟩 🟨О🟨 ⬛Ж⬛ …"""
    em = {"correct": "🟩", "present": "🟨", "absent": "⬛"}
    return " ".join(f"{em[m]}{ch}{em[m]}" for ch, m in zip(guess, marks))

def format_history(attempts: List[Tuple[str, List[str]]]) -> str:
    """Формат всей истории попыток."""
    return "\n".join(format_attempt(g, m) for g, m in attempts)

def letters_aggregate(attempts: List[Tuple[str, List[str]]]) -> Dict[str, str]:
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
    blocks = [(em[st] + ch) if (st := letter_status.get(ch)) else ("▫️" + ch) for ch in order]
    return "\n" + "\n".join([
        "".join(blocks[0:11]),
        "".join(blocks[11:22]),
        "".join(blocks[22:])
    ])

# ===========================
# Рендеринг изображения сетки
# ===========================
try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except Exception:
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore

def _load_cyrillic_font(pixel_size: int):
    """Пытается подобрать шрифт с поддержкой кириллицы на разных ОС."""
    if ImageFont is None:
        return None
    candidates: List[str] = [
        # Имя шрифта, если установлен в системных путях
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
    ]
    # Windows системные шрифты
    windir = os.environ.get("WINDIR", r"C:\\Windows")
    win_fonts = [
        os.path.join(windir, "Fonts", "arialbd.ttf"),
        os.path.join(windir, "Fonts", "arial.ttf"),
        os.path.join(windir, "Fonts", "segoeuib.ttf"),
        os.path.join(windir, "Fonts", "segoeui.ttf"),
        os.path.join(windir, "Fonts", "tahoma.ttf"),
        os.path.join(windir, "Fonts", "calibrib.ttf"),
        os.path.join(windir, "Fonts", "calibri.ttf"),
    ]
    candidates.extend(win_fonts)
    # Linux популярные пути
    candidates.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ])
    for path in candidates:
        try:
            return ImageFont.truetype(path, pixel_size)
        except Exception:
            continue
    return ImageFont.load_default()

def render_attempts_image(attempts: List[Tuple[str, List[str]]]) -> Optional[bytes]:
    """Рендерит PNG-картинку сетки 6x5 с подсветкой букв. Возвращает байты или None, если Pillow недоступен."""
    if Image is None:
        try:
            print("[WARN] Pillow не установлен: изображение сетки не будет отправлено. Установите пакет Pillow.")
        except Exception:
            pass
        return None

    tile = 80
    gap = 10
    padding = 20
    rows = ATTEMPTS
    cols = WORD_LEN

    width = padding * 2 + cols * tile + (cols - 1) * gap
    height = padding * 2 + rows * tile + (rows - 1) * gap

    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    colors = {
        "correct": (106, 170, 100),   # зелёный
        "present": (201, 180, 88),    # жёлтый
        "absent": (120, 124, 126),    # серый
        "empty": (211, 214, 218),     # пустая ячейка
    }
    text_color = (255, 255, 255)
    border_color = (120, 124, 126)

    font = _load_cyrillic_font(int(tile * 0.5))

    # Рисуем сетку
    for r in range(rows):
        for c in range(cols):
            x0 = padding + c * (tile + gap)
            y0 = padding + r * (tile + gap)
            x1 = x0 + tile
            y1 = y0 + tile

            if r < len(attempts):
                guess, marks = attempts[r]
                ch = guess[c]
                status = marks[c]
                fill = colors.get(status, colors["absent"])
            else:
                ch = ""
                fill = colors["empty"]

            draw.rectangle([x0, y0, x1, y1], fill=fill)
            draw.rectangle([x0, y0, x1, y1], outline=border_color, width=2)

            if ch:
                try:
                    bbox = draw.textbbox((0, 0), ch, font=font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]
                except Exception:
                    tw, th = draw.textsize(ch, font=font)  # type: ignore[attr-defined]
                tx = x0 + (tile - tw) // 2
                ty = y0 + (tile - th) // 2 - 2
                draw.text((tx, ty), ch, font=font, fill=text_color)

    bio = BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()

async def reply_with_grid_image(update: Update, attempts: List[Tuple[str, List[str]]]):
    img_bytes = render_attempts_image(attempts)
    if not img_bytes:
        return
    bio = BytesIO(img_bytes)
    # PTB can infer filename from file-like object name if present
    try:
        bio.name = "grid.png"  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        bio.seek(0)
        await update.message.reply_photo(photo=bio)
    except Exception as e:
        try:
            print(f"[ERROR] Не удалось отправить изображение: {e}")
        except Exception:
            pass

def display_name(update: Update) -> str:
    u = update.effective_user
    return (u.first_name or u.username or "Игрок")

def key_chat_id(update: Update) -> int:
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS games (
        chat_id INTEGER PRIMARY KEY,
        answer TEXT NOT NULL,
        attempts_json TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL CHECK(status IN ('IN_PROGRESS','WON','LOST')),
        created_at INTEGER NOT NULL
    );
    """)
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_stats (
        chat_id INTEGER PRIMARY KEY,
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

def update_chat_stats(chat_id: int, won: bool, attempts_count: Optional[int]):
    """Обновляет агрегированную статистику по конкретному чату."""
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM chat_stats WHERE chat_id=?", (chat_id,))
    st = cur.fetchone()
    if st is None:
        cur.execute("INSERT INTO chat_stats(chat_id) VALUES(?)", (chat_id,))
        cur.execute("SELECT * FROM chat_stats WHERE chat_id=?", (chat_id,))
        st = cur.fetchone()

    played = st["played"] + 1
    wins = st["wins"] + (1 if won else 0)
    current_streak = (st["current_streak"] + 1) if won else 0
    max_streak = max(st["max_streak"], current_streak)

    dist = [st[f"dist{i}"] for i in range(1, 7)]
    if won and attempts_count and 1 <= attempts_count <= 6:
        dist[attempts_count - 1] += 1

    cur.execute("""
    UPDATE chat_stats SET played=?, wins=?, current_streak=?, max_streak=?,
        dist1=?,dist2=?,dist3=?,dist4=?,dist5=?,dist6=?
    WHERE chat_id=?
    """, (played, wins, current_streak, max_streak, *dist, chat_id))
    con.commit()
    con.close()

def get_chat_stats(chat_id: int) -> Optional[sqlite3.Row]:
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM chat_stats WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    con.close()
    return row

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
WORDS_ALL: List[str] = []
ANSWER_POOL: List[str] = []

def pick_answer() -> str:
    while True:
        w = random.choice(ANSWER_POOL)
        if len(w) == WORD_LEN and re.fullmatch(r"[А-Я]{"+str(WORD_LEN)+"}", w):
            return w

# ===========================
# Хендлеры
# ===========================
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

    answer = pick_answer()
    print(f"[DEBUG] Загадано для {chat_id}: {answer}")
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
    dist_text = "\n".join(f"{i}: {'▇' * min(st[f'dist{i}'],20)} {st[f'dist{i}']}" for i in range(1,7))
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
        # Игра не идёт — молчим
        return
    
    # Извлекаем слова кириллицей; если не ровно одно слово — игнорируем как не-ход
    tokens = re.findall(r"[А-ЯЁа-яё]+", msg)
    if len(tokens) != 1:
        return

    guess = normalize_word(tokens[0])

    if len(guess) != WORD_LEN:
        await update.message.reply_text(f"Нужно слово из {WORD_LEN} букв.")
        return
    if not re.fullmatch(r"[А-Я]{"+str(WORD_LEN)+"}", guess):
        await update.message.reply_text("Только кириллица, без пробелов и символов.")
        return
    if guess not in WORDS_ALL:
        await update.message.reply_text("Такого слова нет в словаре.")
        return

    answer = g["answer"]
    attempts = json.loads(g["attempts_json"])

    marks = score_guess(guess, answer)
    attempts.append([guess, marks, user_id])

    if guess == answer:
        finish_game_and_update_stats(user_id, True, len(attempts))
        update_chat_stats(chat_id, True, len(attempts))
        clear_game(chat_id)
        kb = letters_aggregate([(a[0], a[1]) for a in attempts])
        await reply_with_grid_image(update, [(a[0], a[1]) for a in attempts])
        # Статистика чата
        st = get_chat_stats(chat_id)
        if st and st["played"]:
            winrate = round(100 * st["wins"] / st["played"])
            dist_text = "\n".join(f"{i}: {'▇' * min(st[f'dist{i}'],20)} {st[f'dist{i}']}" for i in range(1,7))
            await update.message.reply_text(
                f"{guess} — {name}\nПобеда за {len(attempts)} попыток! 🎉\n\n"
                f"Сыграно в чате: {st['played']}\n"
                f"Побед чата: {st['wins']} ({winrate}%)\n"
                f"Серия: {st['current_streak']}, рекорд: {st['max_streak']}\n\n"
                f"Распределение попыток:\n{dist_text}\n/new"
            )
        else:
            await update.message.reply_text(
                f"{guess} — {name}\nПобеда за {len(attempts)} попыток! 🎉\n/new"
            )
        return

    if len(attempts) >= ATTEMPTS:
        update_chat_stats(chat_id, False, None)
        clear_game(chat_id)
        await reply_with_grid_image(update, [(a[0], a[1]) for a in attempts])
        # Статистика чата
        st = get_chat_stats(chat_id)
        if st and st["played"]:
            winrate = round(100 * st["wins"] / st["played"])
            dist_text = "\n".join(f"{i}: {'▇' * min(st[f'dist{i}'],20)} {st[f'dist{i}']}" for i in range(1,7))
            await update.message.reply_text(
                f"{guess} — {name}\nНе вышло. Ответ был: {answer}\n\n"
                f"Сыграно в чате: {st['played']}\n"
                f"Побед чата: {st['wins']} ({winrate}%)\n"
                f"Серия: {st['current_streak']}, рекорд: {st['max_streak']}\n\n"
                f"Распределение попыток:\n{dist_text}\n/new"
            )
        else:
            await update.message.reply_text(f"{guess} — {name}\nНе вышло. Ответ был: {answer}\n/new")
        return

    save_game(chat_id, answer, attempts, "IN_PROGRESS")
    kb = letters_aggregate([(a[0], a[1]) for a in attempts])
    left = ATTEMPTS - len(attempts)
    await reply_with_grid_image(update, [(a[0], a[1]) for a in attempts])
    await update.message.reply_text(
        f"{guess} — {name}\nОсталось попыток: {left}"
    )

# ===========================
# Точка входа
# ===========================
def main():
    global WORDS_ALL, ANSWER_POOL
    init_db()
    WORDS_ALL = load_words(WORDS_FILE, WORD_LEN, min_count=1000)
    ANSWER_POOL = load_words(POOL_FILE, WORD_LEN, min_count=1)
    inter = sorted(set(ANSWER_POOL) & set(WORDS_ALL))
    if not inter:
        raise RuntimeError("ANSWER_POOL не пересекается с WORDS_ALL")
    ANSWER_POOL = inter

    if not TOKEN:
        raise RuntimeError("Нужен TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("giveup", cmd_giveup))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print(f"Загружено слов: {len(WORDS_ALL)}; пул загадок: {len(ANSWER_POOL)}. Бот запущен.")
    app.run_polling()

if __name__ == "__main__":
    main()
