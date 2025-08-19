#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from pathlib import Path
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, ContextTypes, filters
)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Нужно задать TELEGRAM_BOT_TOKEN")

MAP_FILE = Path("emoji_map.json")

def load_map() -> dict:
    if MAP_FILE.exists():
        return json.loads(MAP_FILE.read_text(encoding="utf-8"))
    return {}

def save_map(mapping: dict):
    MAP_FILE.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

async def on_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.entities:
        return

    text = msg.text or ""
    mapping = load_map()
    updated = False

    for ent in msg.entities:
        if ent.type == "custom_emoji":
            ce_id = ent.custom_emoji_id
            # предполагаем формат "🅰 А"
            suffix = text[ent.offset + ent.length:].strip()
            letter = suffix[0].upper() if suffix else None
            if letter and letter.isalpha():
                mapping[letter] = ce_id
                updated = True

    if updated:
        save_map(mapping)
        await msg.reply_text(f"Сохранил: {letter} → {ce_id}\nВсего {len(mapping)} записей.")
    else:
        await msg.reply_text("Не смог определить букву. Формат: <эмодзи> <буква>")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & filters.Entity("custom_emoji"), on_emoji))
    print("Граббер запущен. Кидай: <эмодзи> <буква>. Результат в emoji_map.json")
    app.run_polling()

if __name__ == "__main__":
    main()
