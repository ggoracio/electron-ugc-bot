#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TG-бот «Электрон UGC»
• /start – приветствие + клавиатура «📢 Идея / 💬 Фидбек»
• пользователь пишет идею/фидбек ➜ бот пересылает её в мод-чат
• в мод-чате под сообщением – «✅ Принять / ❌ Отклонить»
• после нажатия модератором бот отвечает автору
"""

import asyncio
import logging
import os
from typing import Dict

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery,
    KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- НАСТРОЙКИ ----------------------------------------------------------------
BOT_TOKEN   = os.getenv("BOT_TOKEN",   "PASTE_YOUR_TOKEN")
MOD_CHAT_ID = int(os.getenv("MOD_CHAT_ID", "-1001234567890"))  # супергруппа-модератор

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

bot  = Bot(BOT_TOKEN, parse_mode="HTML")
dp   = Dispatcher()

# чтобы по callback data получить id автора
pending: Dict[str, int] = {}                 # callback_id → user_id
# -----------------------------------------------------------------------------

def main_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.add(
        KeyboardButton(text="📢 Идея"),
        KeyboardButton(text="💬 Фидбек"),
    )
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

@dp.message(CommandStart())
async def start(m: Message):
    await m.answer(
        "Привет! Поделись идеей или фидбеком – выбери действие кнопкой 👇",
        reply_markup=main_keyboard()
    )

@dp.message(F.text.in_(["📢 Идея", "💬 Фидбек"]))
async def choose_type(m: Message):
    tag = "idea" if m.text.startswith("📢") else "feedback"
    await m.answer(
        "Опиши подробно. Когда закончишь, просто отправь сообщение. "
        "Я передам его команде ✨"
    )
    # сохраняем выбранный тип во временный state через message.chat_data
    await dp.storage.set_data(chat=m.chat.id, data={"tag": tag})

@dp.message()
async def idea(m: Message):
    data = await dp.storage.get_data(chat=m.chat.id)
    if "tag" not in data:
        return  # юзер прислал что-то до выбора типа – игнорим
    tag = data["tag"]
    # генерируем уникальный callback-id
    cb_id = f"{m.chat.id}_{m.message_id}"
    pending[cb_id] = m.chat.id

    # пересылаем в мод-чат
    caption = (
        f"<b>Новая { 'идея' if tag=='idea' else 'обратная связь' }</b>\n"
        f"От: <a href='tg://user?id={m.from_user.id}'>{m.from_user.full_name}</a>\n\n"
        f"{m.text}"
    )
    btn_ok = InlineKeyboardButton(text="✅ Принять",   callback_data=f"ok|{cb_id}")
    btn_no = InlineKeyboardButton(text="❌ Отклонить", callback_data=f"no|{cb_id}")
    ikb = InlineKeyboardMarkup(inline_keyboard=[[btn_ok, btn_no]])
    await bot.send_message(chat_id=MOD_CHAT_ID, text=caption, reply_markup=ikb)

    await m.answer("Спасибо! Идея отправлена на рассмотрение ✅", reply_markup=main_keyboard())
    await dp.storage.set_data(chat=m.chat.id, data={})  # сбрасываем state

@dp.callback_query(F.data.startswith(("ok|", "no|")))
async def moderation(cb: CallbackQuery):
    verdict, cb_id = cb.data.split("|", 1)
    if cb_id not in pending:
        await cb.answer("Уже обработано", show_alert=True)
        return
    user_id = pending.pop(cb_id)

    if verdict == "ok":
        text_to_user = "Ваша идея принята! Благодарим 💙"
        note = "✅ Одобрено"
    else:
        text_to_user = "Спасибо, но пока реализовать не можем 🙏"
        note = "❌ Отклонено"

    # уведомляем автора
    try:
        await bot.send_message(user_id, text_to_user)
    except Exception as e:
        logging.warning(f"Не удалось написать пользователю {user_id}: {e}")

    # помечаем сообщение в мод-чате
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.reply(note)
    await cb.answer("Готово")

async def main():
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
