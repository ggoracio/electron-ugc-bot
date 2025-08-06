"""
Electron UGC Bot (минимальный рабочий каркас)
aiogram 3.x
"""

# ─── Импорты ────────────────────────────────────────────────────────────────
import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.types import Message, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# ─── Конфигурация ──────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")                 # задаётся в Railway Variables
if not BOT_TOKEN:
    raise RuntimeError("Переменная BOT_TOKEN не найдена!")

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)  # единый parse_mode
)
dp = Dispatcher()

# ─── Клавиатура главного меню ──────────────────────────────────────────────
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.add(
        KeyboardButton(text="/idea"),
        KeyboardButton(text="/feedback"),
    )
    kb.adjust(2)                         # 2 кнопки в строке
    return kb.as_markup(resize_keyboard=True)

# ─── Хэндлеры ──────────────────────────────────────────────────────────────
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот Электрона для сбора идей и обратной связи.\n"
        "Нажмите /idea или /feedback.",
        reply_markup=main_menu(),
    )

@dp.message(F.text == "/idea")
async def cmd_idea(message: Message):
    await message.answer("Опишите вашу идею одним сообщением. Спасибо!")

@dp.message(F.text == "/feedback")
async def cmd_feedback(message: Message):
    await message.answer("Оставьте обратную связь — мы обязательно прочитаем.")

# ─── Запуск ────────────────────────────────────────────────────────────────
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
