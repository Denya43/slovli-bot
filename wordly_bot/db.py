import json
import sqlite3
import time
from typing import List, Optional

from .config import DB_FILE


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    con = db()
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS games (
            chat_id INTEGER PRIMARY KEY,
            answer TEXT NOT NULL,
            attempts_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL CHECK(status IN ('IN_PROGRESS','WON','LOST')),
            created_at INTEGER NOT NULL
        );
        """
    )
    cur.execute(
        """
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
        """
    )
    cur.execute(
        """
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
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_user_wins (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            wins INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(chat_id, user_id)
        );
        """
    )
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
    cur.execute(
        """
        INSERT INTO games(chat_id, answer, attempts_json, status, created_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(chat_id) DO UPDATE SET
            answer=excluded.answer,
            attempts_json=excluded.attempts_json,
            status=excluded.status,
            created_at=excluded.created_at
        """,
        (chat_id, answer, json.dumps(attempts, ensure_ascii=False), status, int(time.time())),
    )
    con.commit()
    con.close()


def clear_game(chat_id: int):
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM games WHERE chat_id=?", (chat_id,))
    con.commit()
    con.close()


def finish_game_and_update_stats(
    winner_user_id: Optional[int], won: bool, attempts_count: Optional[int]
):
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

    cur.execute(
        """
        UPDATE stats SET played=?, wins=?, current_streak=?, max_streak=?,
            dist1=?,dist2=?,dist3=?,dist4=?,dist5=?,dist6=?
        WHERE user_id=?
        """,
        (played, wins, current_streak, max_streak, *dist, winner_user_id),
    )
    con.commit()
    con.close()


def update_chat_stats(chat_id: int, won: bool, attempts_count: Optional[int]):
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

    cur.execute(
        """
        UPDATE chat_stats SET played=?, wins=?, current_streak=?, max_streak=?,
            dist1=?,dist2=?,dist3=?,dist4=?,dist5=?,dist6=?
        WHERE chat_id=?
        """,
        (played, wins, current_streak, max_streak, *dist, chat_id),
    )
    con.commit()
    con.close()


def get_stats(user_id: int) -> Optional[sqlite3.Row]:
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM stats WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row


def get_chat_stats(chat_id: int) -> Optional[sqlite3.Row]:
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM chat_stats WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    con.close()
    return row


def record_chat_win(chat_id: int, user_id: int, name: str):
    """Увеличивает счёт побед пользователя внутри конкретного чата и обновляет имя."""
    con = db()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO chat_user_wins(chat_id, user_id, name, wins)
        VALUES(?, ?, ?, 1)
        ON CONFLICT(chat_id, user_id) DO UPDATE SET
            wins = chat_user_wins.wins + 1,
            name = excluded.name
        """,
        (chat_id, user_id, name),
    )
    con.commit()
    con.close()


def get_chat_leaderboard(chat_id: int, limit: int = 10) -> List[sqlite3.Row]:
    con = db()
    cur = con.cursor()
    cur.execute(
        """
        SELECT user_id, name, wins
        FROM chat_user_wins
        WHERE chat_id=?
        ORDER BY wins DESC, name ASC
        LIMIT ?
        """,
        (chat_id, limit),
    )
    rows = cur.fetchall()
    con.close()
    return rows



