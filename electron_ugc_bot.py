#!/usr/bin/env python3
# electron_ugc_bot.py
# Полностью рабочая версия (aiogram 3)

import os
import logging
import asyncio

from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.client.default import DefaultBotProperties

# ─────────────────── настройки ───────────────────
BOT_TOKEN   = os.getenv("BOT_TOKEN", "8238527161:AAHoOVEMJWhWH_wPyZ2YhInOEWL-KxYZHk8")
MOD_CHAT_ID = int(os.getenv("MOD_CHAT_ID", "-4831345051"))  # id модераторского чата

# ────────────────── инициализация ─────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

bot     = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp      = Dispatcher()
router  = Router()
dp.include_router(router)

# ──────────────── хендлер идеи ────────────────
@router.message(F.text)
async def idea(msg: Message) -> None:
    """
    Принимает любое текстовое сообщение от пользователя-автора,
    копирует его в модераторский чат и отправляет карточку с кнопками.
    """
    # 1) копируем оригинал без клавиатуры
    await bot.copy_message(
        chat_id=MOD_CHAT_ID,
        from_chat_id=msg.chat.id,
        message_id=msg.message_id,
    )

    # 2) карточка-уведомление с inline-кнопками
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Одобрить", callback_data="approve"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data="reject"),
        ]]
    )

    await bot.send_message(
        MOD_CHAT_ID,
        f"<b>Новая идея от "
        f"{'@' + msg.from_user.username if msg.from_user.username else msg.from_user.id}</b>",
        reply_markup=kb,
    )

    # 3) ответ автору
    await msg.answer("✅ Спасибо! Ваша идея отправлена модераторам.")

# ──────────────── обработка кнопок ────────────────
@router.callback_query(F.data == "approve")
async def on_approve(cb: CallbackQuery) -> None:
    await cb.answer("Одобрено")
    await cb.message.edit_text(cb.message.text + "\n\n✔️ <b>Одобрено</b>")

@router.callback_query(F.data == "reject")
async def on_reject(cb: CallbackQuery) -> None:
    await cb.answer("Отклонено")
    await cb.message.edit_text(cb.message.text + "\n\n❌ <b>Отклонено</b>")

# ───────────────────── main ───────────────────────
async def main() -> None:
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
