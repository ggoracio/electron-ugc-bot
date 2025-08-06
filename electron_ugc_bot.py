"""
Electron UGC Bot – принимает идеи / feedback и шлёт их в модераторский чат
aiogram-3
"""

import os
import asyncio
from collections import defaultdict

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.types import (
    Message,
    KeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# ────────────────── конфигурация ────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

if not BOT_TOKEN or not ADMIN_CHAT_ID:
    raise RuntimeError("Нужны переменные BOT_TOKEN и ADMIN_CHAT_ID")

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ────────────────── клавиатура ──────────────────────
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.add(
    KeyboardButton(text="/idea"),
    KeyboardButton(text="/feedback")
    )
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# ────────────────── простейшее состояние ────────────
waiting_for = defaultdict(lambda: None)        # user_id → "idea"/"fb"/None

# ────────────────── хэндлеры команд ────────────────
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    waiting_for.pop(message.from_user.id, None)
    await message.answer(
        "Привет! Я бот Электрона – собираю идеи и обратную связь.\n"
        "Нажмите /idea или /feedback.",
        reply_markup=main_menu(),
    )

@dp.message(F.text == "/idea")
async def cmd_idea(message: Message):
    waiting_for[message.from_user.id] = "idea"
    await message.answer(
        "Опишите вашу идею одним сообщением. После отправки её увидят модераторы 📩"
    )

@dp.message(F.text == "/feedback")
async def cmd_feedback(message: Message):
    waiting_for[message.from_user.id] = "fb"
    await message.answer(
        "Оставьте обратную связь одним сообщением – мы обязательно прочитаем 🙂"
    )

# ────────────────── приём одноразового ответа ───────
@dp.message()
async def catcher(message: Message):
    state = waiting_for.get(message.from_user.id)
    if state is None:       # пользователь не в режиме ввода
        return
    # формируем текст для админ-чата
    kind = "💡 <b>Новая идея</b>" if state == "idea" else "✉️ <b>Feedback</b>"
    text = (
        f"{kind}\n"
        f"<b>От:</b> {message.from_user.full_name} (<code>{message.from_user.id}</code>)\n"
        f"<b>Текст:</b>\n{message.html_text}"
    )
    await bot.send_message(ADMIN_CHAT_ID, text)
    await message.answer("Спасибо! Ваше сообщение отправлено модераторам 🙌")

    waiting_for.pop(message.from_user.id, None)   # сбрасываем состояние

# ────────────────── запуск бота ─────────────────────
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
