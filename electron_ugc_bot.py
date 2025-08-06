# electron_ugc_bot.py
# ─────────────────────────────────────────────────────────────────────────────
# Бот-черновик: собирает идеи и обратную связь от сотрудников
# Требуется переменная окружения BOT_TOKEN
# ─────────────────────────────────────────────────────────────────────────────
import os
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.types import (
    Message,
    KeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# ───- проверяем токен ────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("⚠️  Переменная окружения BOT_TOKEN не установлена!")

# ───- инициализируем бота и диспетчер ───────────────────────────────────────
bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)  # единый parse_mode
)
dp = Dispatcher()

# ───- построение клавиатуры главного меню ───────────────────────────────────
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.add(
        KeyboardButton(text="/idea"),
        KeyboardButton(text="/feedback"),
    )
    kb.adjust(2)                        # две кнопки в строке
    return kb.as_markup(resize_keyboard=True)

# ───- хэндлеры команд ────────────────────────────────────────────────────────
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для сбора идей и обратной связи. "
        "Выберите действие:",
        reply_markup=main_menu(),
    )

@dp.message(F.text == "/idea")
async def cmd_idea(message: Message):
    await message.answer(
        "Опишите вашу идею одним сообщением. "
        "После отправки модераторы её увидят. 🙌"
    )

@dp.message(F.text == "/feedback")
async def cmd_feedback(message: Message):
    await message.answer(
        "Оставьте обратную связь, предложение или замечание — всё читаем!"
    )

# ───- запуск поллинга ───────────────────────────────────────────────────────
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    main()
