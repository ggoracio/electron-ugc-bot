import logging
import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ParseMode,
)

# ─────────── настройки ───────────
BOT_TOKEN    = os.getenv("BOT_TOKEN")          # задайте в переменных окружения
MOD_CHAT_ID  = int(os.getenv("MOD_CHAT_ID"))   # id супергруппы-модерации (-100…)

if not BOT_TOKEN or not MOD_CHAT_ID:
    raise SystemExit("❌  BOT_TOKEN или MOD_CHAT_ID не заданы!")

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp  = Dispatcher()

# ─────────── клавиатуры ───────────
choice_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💡 Идея",   callback_data="idea")],
        [InlineKeyboardButton(text="✉️ Фидбэк", callback_data="feedback")],
    ]
)

decision_kb = lambda from_id: InlineKeyboardMarkup(
    inline_keyboard=[[
        InlineKeyboardButton("✅ Принять",  callback_data=f"accept:{from_id}"),
        InlineKeyboardButton("🚫 Отклонить", callback_data=f"reject:{from_id}")
    ]]
)

restart_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton("↩️ Ещё сообщение", callback_data="restart")]]
)

# ─────────── сценарий пользователя ───────────
@dp.message(Command("start"))
async def start(m: Message):
    await m.answer(
        "Привет! Что хотите отправить?",
        reply_markup=choice_kb
    )

@dp.callback_query(F.data.in_({"idea", "feedback"}))
async def choose_type(c: CallbackQuery):
    tag = "💡 Идея" if c.data == "idea" else "✉️ Фидбэк"
    await c.message.answer(f"Хорошо, напишите {tag.lower()} одним сообщением.")
    # запоминаем выбранный тип прямо в callback_data next step
    await dp.storage.update_state(chat=c.message.chat.id, user=c.from_user.id, state=c.data)
    await c.answer()

@dp.message()  # ловим любое текстовое сообщение, когда есть сохранённое state
async def receive_text(m: Message, state: str | None):
    if state not in {"idea", "feedback"}:
        return  # пользователь написал «лишнее» — игнорируем

    tag = "💡 <b>Идея</b>" if state == "idea" else "✉️ <b>Фидбэк</b>"
    sent = await bot.send_message(
        MOD_CHAT_ID,
        f"{tag}\n\n{m.html_text}\n\n<b>От:</b> <a href='tg://user?id={m.from_user.id}'>{m.from_user.full_name}</a>",
        reply_markup=decision_kb(m.from_user.id)
    )

    await m.answer("Сообщение отправлено на модерацию ✅", reply_markup=restart_kb)
    # очищаем state
    await dp.storage.update_state(chat=m.chat.id, user=m.from_user.id, state=None)

# ─────────── сценарий модератора ───────────
@dp.callback_query(F.data.startswith(("accept", "reject")))
async def moderator_action(c: CallbackQuery):
    action, user_id = c.data.split(":")
    user_id = int(user_id)

    if action == "accept":
        await bot.send_message(user_id, "Спасибо! Ваше сообщение принято 👌", reply_markup=restart_kb)
        await c.message.edit_reply_markup()  # убираем кнопки
        await c.answer("Принято")
    else:
        await bot.send_message(user_id, "К сожалению, сообщение отклонено 🙏", reply_markup=restart_kb)
        await c.message.edit_reply_markup()
        await c.answer("Отклонено")

# ─────────── restarts без /start ───────────
@dp.callback_query(F.data == "restart")
async def restart(c: CallbackQuery):
    await c.message.answer("Что хотите отправить?", reply_markup=choice_kb)
    await c.answer()

# ─────────── запуск ───────────
async def main():
    logging.info("Bot is starting…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
