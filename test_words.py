#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки загрузки слов разной длины
"""

import os
import re
from pathlib import Path
from typing import List

def load_words(path: str, length: int, *, min_count: int = 100) -> List[str]:
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
                print(f"Предупреждение: слов мало: {len(words)} для длины {length}")
            return words
        except Exception as e:
            tried.append(enc)
            last_err = e

    raise RuntimeError(f"Не удалось прочитать {path} (пробовал: {', '.join(tried)}). {last_err}")

def main():
    words_file = "words.txt"
    
    print("Тестирование загрузки слов из", words_file)
    print("=" * 50)
    
    total_words = 0
    for length in range(4, 10):
        try:
            words = load_words(words_file, length, min_count=10)
            print(f"Длина {length}: {len(words)} слов")
            if words:
                print(f"  Примеры: {', '.join(words[:5])}")
                if len(words) > 5:
                    print(f"  ... и еще {len(words) - 5}")
            total_words += len(words)
        except Exception as e:
            print(f"Длина {length}: Ошибка - {e}")
    
    print("=" * 50)
    print(f"Всего слов: {total_words}")

if __name__ == "__main__":
    main()
