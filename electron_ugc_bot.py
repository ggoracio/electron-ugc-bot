# electron_ugc_bot.py
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)

# ──────────────────────────────────────
# 1.  НАСТРОЙКИ
# ──────────────────────────────────────
BOT_TOKEN         = os.getenv("8238527161:AAHoOVEMJWhWH_wPyZ2YhInOEWL-KxYZHk8")                      # токен бота
MODERATOR_CHAT_ID = int(os.getenv("MOD_CHAT_ID", "-4831345051"))      # id супергруппы

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp  = Dispatcher()

# ──────────────────────────────────────
# 2.  СОСТОЯНИЯ
# ──────────────────────────────────────
class Form(StatesGroup):
    choosing = State()   # пользователь выбрал тип (идея/фидбек)
    writing  = State()   # пишет текст

# ──────────────────────────────────────
# 3.  КНОПКИ
# ──────────────────────────────────────
reply_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💡 Идея"),
         KeyboardButton(text="📝 Фидбек")]
    ],
    resize_keyboard=True
)

def mod_inline(msg_id: int, user_id: int) -> InlineKeyboardMarkup:
    # в callback-data сразу передаём id исходного сообщения и автора
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить",
                                  callback_data=f"approve:{msg_id}:{user_id}")],
            [InlineKeyboardButton(text="✏️ Правки",
                                  callback_data=f"edit:{msg_id}:{user_id}")],
            [InlineKeyboardButton(text="❌ Отклонить",
                                  callback_data=f"reject:{msg_id}:{user_id}")]
        ]
    )

# ──────────────────────────────────────
# 4.  ОБРАБОТЧИКИ
# ──────────────────────────────────────
@dp.message(CommandStart())
async def start(m: types.Message, state: FSMContext):
    await m.reply(
        "Привет! Поделитесь <b>идеей</b> или оставьте <b>фидбек</b> 🙂",
        reply_markup=reply_kb
    )
    await state.set_state(Form.choosing)

# выбор типа
@dp.message(F.text.in_(["💡 Идея", "📝 Фидбек"]), Form.choosing)
async def choose_type(m: types.Message, state: FSMContext):
    tag = "IDEA" if "Идея" in m.text else "FEEDBACK"
    await state.update_data(tag=tag)
    await m.reply("Напишите текст и отправьте одним сообщением ✉️",
                  reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Form.writing)

# получение текста от пользователя
@dp.message(Form.writing, F.text)
async def receive_text(m: types.Message, state: FSMContext):
    data = await state.get_data()
    tag  = data["tag"]
    # пересылаем в модчаты с inline-кнопками
    sent = await bot.copy_message(
        chat_id=MODERATOR_CHAT_ID,
        from_chat_id=m.chat.id,
        message_id=m.message_id,
        caption=f"<b>{tag}</b> от <a href='tg://user?id={m.from_user.id}'>{m.from_user.full_name}</a>\n\n{m.text}"
    )
    # добавляем кнопки
    await bot.edit_message_reply_markup(
        chat_id=MODERATOR_CHAT_ID,
        message_id=sent.message_id,
        reply_markup=mod_inline(sent.message_id, m.from_user.id)
    )
    await m.reply("Спасибо! Ваша запись отправлена на модерацию. ✅")
    await state.clear()

# обработка нажатий модератора
@dp.callback_query(F.data.regexp(r"^(approve|edit|reject):"))
async def moderation_action(cq: types.CallbackQuery):
    action, msg_id, user_id = cq.data.split(":")
    user_id = int(user_id)

    if action == "approve":
        text = "Ваша идея одобрена! 🎉"
    elif action == "edit":
        text = "Спасибо! Есть пара уточнений по вашей идее; мы свяжемся позже. ✏️"
    else:  # reject
        text = "К сожалению, ваша идея не подошла. Но не останавливайтесь! ❌"

    # сообщаем автору
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        logging.warning(f"Не удалось написать пользователю {user_id}: {e}")

    # помечаем в модчате
    await cq.message.edit_reply_markup()  # убираем кнопки
    await cq.answer("Готово!")

# ──────────────────────────────────────
# 5.  ЗАПУСК
# ──────────────────────────────────────
async def main():
    logging.info("Bot is starting…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

