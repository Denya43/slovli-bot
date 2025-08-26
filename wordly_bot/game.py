import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import WORD_LEN


def normalize_word(w: str) -> str:
    w = w.strip().upper()
    w = w.replace("Ё", "Е")
    w = re.sub(r"[^А-Я]", "", w)
    return w


def load_words(path: str, length: int, *, min_count: int = 1000) -> List[str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Не найден файл словаря: {path}")

    encodings = ["utf-8", "utf-8-sig", "cp1251", "koi8-r", "mac_cyrillic"]

    last_err = None
    tried: List[str] = []

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
        except Exception as e:  # noqa: BLE001
            tried.append(enc)
            last_err = e

    raise RuntimeError(
        f"Не удалось прочитать {path} (пробовал: {', '.join(tried)}). {last_err}"
    )


def score_guess(guess: str, answer: str) -> List[str]:
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
    em = {"correct": "🟩", "present": "🟨", "absent": "⬛"}
    return " ".join(f"{em[m]}{ch}{em[m]}" for ch, m in zip(guess, marks))


def format_history(attempts: List[Tuple[str, List[str]]]) -> str:
    return "\n".join(format_attempt(g, m) for g, m in attempts)


def letters_aggregate(attempts: List[Tuple[str, List[str]]]) -> Dict[str, str]:
    best: Dict[str, str] = {}
    rank = {"correct": 3, "present": 2, "absent": 1}
    for guess, marks in attempts:
        for ch, m in zip(guess, marks):
            if ch not in best or rank[m] > rank[best[ch]]:
                best[ch] = m
    return best


def pick_answer(pool: List[str], word_length: int = 5) -> str:
    while True:
        w = random.choice(pool)
        if len(w) == word_length and re.fullmatch(r"[А-Я]{" + str(word_length) + "}", w):
            return w


def get_words_for_length(word_length: int, base_words: List[str], custom_words: List[str]) -> List[str]:
    """Получить все слова для заданной длины (включая пользовательские)"""
    return base_words + custom_words



