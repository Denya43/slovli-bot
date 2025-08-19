from pathlib import Path
import re
import sys

WORD_LEN = 5

def normalize_word(w: str) -> str:
    w = w.strip().upper()
    w = w.replace("Ё", "Е")
    w = re.sub(r"[^А-Я]", "", w)
    return w

def main():
    if len(sys.argv) < 3:
        print("Usage: python prepare_words.py output_words.txt input1.txt [input2.txt ...]")
        sys.exit(1)
    out = Path(sys.argv[1])
    seen = set()
    kept = []
    for src in sys.argv[2:]:
        p = Path(src)
        if not p.exists():
            print(f"Файл не найден: {p}")
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        # Берём слова, разделенные любыми не-кириллическими символами
        for raw in re.split(r"\W+", text, flags=re.UNICODE):
            w = normalize_word(raw)
            if len(w) == WORD_LEN and w and w not in seen:
                seen.add(w)
                kept.append(w)
    kept.sort()
    out.write_text("\n".join(kept), encoding="utf-8")
    print(f"Готово: {out} ({len(kept)} слов)")

if __name__ == "__main__":
    main()
