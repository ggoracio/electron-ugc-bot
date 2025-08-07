# electron_ugc_bot.py
import os
import re
import logging
import asyncio

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from dotenv import load_dotenv   # pip install python-dotenv

# --------------------------------------------------------------------------- #
# 1. Конфигурация

load_dotenv()                              # берем переменные из .env (Railway тоже видит)
BOT_TOKEN    = os.getenv("BOT_TOKEN")
MOD_CHAT_ID  = int(os.getenv("MOD_CHAT_ID", "0"))   # id супергруппы-модераторов

logging.basicConfig(level=logging.INFO)
bot  = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp   = Dispatcher(storage=MemoryStorage())          # простейшее FSM-хранилище

# простая “база” — запоминаем сообщение-модерации -> (user_id, tag).
PENDING: dict[int, tuple[int, str]] = {}

# --------------------------------------------------------------------------- #
# 2. Клавиатуры

main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="💡 Идея"),
               KeyboardButton(text="✉️ Фидбек")]],
    resize_keyboard=True
)

again_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="↻ Отправить ещё")]],
    resize_keyboard=True
)

def mod_kb(user_id: int, tag: str):
    """Кнопки для модераторов"""
    cb_approve = f"approve:{user_id}:{tag}"
    cb_reject  = f"reject:{user_id}:{tag}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять",  callback_data=cb_approve),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=cb_reject)]
    ])

# --------------------------------------------------------------------------- #
# 3. Хэндлеры пользователя

@dp.message(CommandStart())
async def cmd_start(m: types.Message):
    await m.answer(
        "Привет! Выберите, что хотите отправить ⤵️",
        reply_markup=main_kb
    )

@dp.message(F.text.in_(["💡 Идея", "✉️ Фидбек", "↻ Отправить ещё"]))
async def choose_type(m: types.Message, state: types.FSMContext):
    tag = "idea" if "Идея" in m.text else "feedback"
    await state.update_data(tag=tag)            # сохраняем выбранный тип
    await m.answer(
        f"Введите текст { 'идеи' if tag=='idea' else 'фидбека' }:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(~Command("start"))
async def receive_text(m: types.Message, state: types.FSMContext):
    data = await state.get_data()
    tag  = data.get("tag")
    if not tag:       # если пользователь написал, не выбрав тип
        await m.answer("Сперва выберите <b>Идею</b> или <b>Фидбек</b>.", reply_markup=main_kb)
        return

    caption = f"<b>{'Идея' if tag=='idea' else 'Фидбек'}</b> от <a href='tg://user?id={m.from_user.id}'>{m.from_user.full_name}</a>\n\n{m.text}"
    sent = await bot.send_message(
        chat_id=MOD_CHAT_ID,
        text=caption,
        reply_markup=mod_kb(m.from_user.id, tag)
    )
    # запоминаем, чтобы потом понять, кому отвечать
    PENDING[sent.message_id] = (m.from_user.id, tag)

    await m.answer(
        "Спасибо! Сообщение отправлено на модерацию ✅",
        reply_markup=again_kb
    )
    await state.clear()

# --------------------------------------------------------------------------- #
# 4. Хэндлеры модератора

@dp.callback_query(F.data.regexp(r"^(approve|reject):(\d+):(\w+)$"))
async def mod_action(cq: types.CallbackQuery):
    action, user_id, tag = re.match(r"^(approve|reject):(\d+):(\w+)$", cq.data).groups()
    user_id = int(user_id)

    # обновляем текст в групповом сообщении
    status_text = "✅ Принято" if action == "approve" else "❌ Отклонено"
    new_caption = cq.message.html_text + f"\n\n<b>{status_text}</b>"
    await cq.message.edit_text(new_caption)     # уберём кнопки после решения
    await cq.answer("Готово")

    # уведомляем автора
    try:
        note = "✅ Мы приняли вашу идею. Спасибо!" if action == "approve" \
             else "❌ К сожалению, ваша идея не подошла."
        await bot.send_message(user_id, note, reply_markup=again_kb)
    except Exception as e:
        logging.warning(f"Не удалось уведомить пользователя {user_id}: {e}")

    # чистим “базу”
    PENDING.pop(cq.message.message_id, None)

# --------------------------------------------------------------------------- #
# 5. Запуск

if __name__ == "__main__":
    logging.info("Bot is starting…")
    asyncio.run(dp.start_polling(bot))
