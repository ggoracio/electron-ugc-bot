# electron_ugc_bot.py
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)

# ──────────────────────────────────────
# 1.  НАСТРОЙКИ
# ──────────────────────────────────────
BOT_TOKEN         = os.getenv("BOT_TOKEN")
MODERATOR_CHAT_ID = int(os.getenv("MOD_CHAT_ID", 0))

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp  = Dispatcher()

# ──────────────────────────────────────
# 2.  СОСТОЯНИЯ
# ──────────────────────────────────────
class Form(StatesGroup):
    welcomed = State()   # ждём нажатия «Приступить»
    choosing = State()   # пользователь выбирает «Идея/Фидбек»
    writing  = State()   # пишет текст

# ──────────────────────────────────────
# 3.  КНОПКИ
# ──────────────────────────────────────
def begin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🚀 Приступить", callback_data="begin")
        ]]
    )

reply_kb = ReplyKeyboardMarkup(
    keyboard=[[
        KeyboardButton(text="💡 Идея"),
        KeyboardButton(text="📝 Фидбек")
    ]],
    resize_keyboard=True
)

def restart_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="↩ Предложить ещё идею", callback_data="restart")
        ]]
    )

def mod_inline(msg_id: int, user_id: int) -> InlineKeyboardMarkup:
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
async def cmd_start(m: types.Message, state: FSMContext):
    """Приветственное сообщение + «Приступить»."""
    await state.clear()
    await m.answer(
        "👋 <b>Привет!</b>\n\n"
        "Здесь вы можете поделиться свежей <b>идеей</b> или оставить <b>фидбек</b>.\n"
        "Нажмите кнопку ниже, чтобы начать.",
        reply_markup=begin_kb()
    )
    await state.set_state(Form.welcomed)

# нажали «Приступить»
@dp.callback_query(F.data == "begin", Form.welcomed)
async def cb_begin(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(
        "Отлично! Что вы хотите отправить?",
        reply_markup=reply_kb
    )
    await state.set_state(Form.choosing)
    await cb.answer()

# выбор типа
@dp.message(Form.choosing, F.text.in_(["💡 Идея", "📝 Фидбек"]))
async def choose_type(m: types.Message, state: FSMContext):
    tag = "IDEA" if "Идея" in m.text else "FEEDBACK"
    await state.update_data(tag=tag)
    await m.answer(
        "Напишите текст и отправьте одним сообщением ✉️",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(Form.writing)

# получение текста
@dp.message(Form.writing, F.text)
async def receive_text(m: types.Message, state: FSMContext):
    data = await state.get_data()
    tag  = data["tag"]

    sent = await bot.copy_message(
        chat_id=MODERATOR_CHAT_ID,
        from_chat_id=m.chat.id,
        message_id=m.message_id,
        caption=f"<b>{tag}</b> от "
                f"<a href='tg://user?id={m.from_user.id}'>{m.from_user.full_name}</a>\n\n{m.text}"
    )
    await bot.edit_message_reply_markup(
        chat_id=MODERATOR_CHAT_ID,
        message_id=sent.message_id,
        reply_markup=mod_inline(sent.message_id, m.from_user.id)
    )

    await m.answer(
        "Спасибо! Ваша запись отправлена на модерацию. ✅",
        reply_markup=restart_kb()
    )
    await state.clear()

# «Предложить ещё идею»
@dp.callback_query(F.data == "restart")
async def restart(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    # сразу показываем выбор «идея/фидбек», минуя приветствие
    await cb.message.answer(
        "Что вы хотите отправить?",
        reply_markup=reply_kb
    )
    await state.set_state(Form.choosing)

# обработка нажатий модератора
@dp.callback_query(F.data.regexp(r"^(approve|edit|reject):"))
async def moderation_action(cb: types.CallbackQuery):
    action, msg_id, user_id = cb.data.split(":")
    user_id = int(user_id)

    if action == "approve":
        text = "Ваша идея одобрена! 🎉"
    elif action == "edit":
        text = "Спасибо! Есть пара уточнений по вашей идее; мы свяжемся позже. ✏️"
    else:
        text = "К сожалению, ваша идея не подошла. Но не останавливайтесь! ❌"

    try:
        await bot.send_message(user_id, text, reply_markup=restart_kb())
    except Exception as e:
        logging.warning(f"Не удалось написать пользователю {user_id}: {e}")

    await cb.message.edit_reply_markup()  # убираем кнопки модератора
    await cb.answer("Готово!")

# ──────────────────────────────────────
# 5.  ЗАПУСК
# ──────────────────────────────────────
async def main():
    logging.info("Bot is starting…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
