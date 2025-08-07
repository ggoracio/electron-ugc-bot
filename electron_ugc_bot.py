# electron_ugc_bot.py
import asyncio
import logging
import os
from typing import Dict

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)

# ─────────────── 1.  НАСТРОЙКИ ───────────────
BOT_TOKEN         = os.getenv("BOT_TOKEN")
MODERATOR_CHAT_ID = int(os.getenv("MOD_CHAT_ID", 0))

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp  = Dispatcher()

MSG2USER: Dict[int, int] = {}          # id карточки ➜ id автора

# ─────────────── 2.  СОСТОЯНИЯ ───────────────
class Form(StatesGroup):
    welcomed = State()
    choosing = State()
    writing  = State()

# ─────────────── 3.  КНОПКИ ───────────────
def begin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Приступить", callback_data="begin")]  # ← исправлено
        ]
    )

reply_kb = ReplyKeyboardMarkup(
    keyboard=[[
        KeyboardButton(text="💡 Идея"),   # ← исправлено
        KeyboardButton(text="📝 Фидбек")  # ← исправлено
    ]],
    resize_keyboard=True
)

def restart_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩ Предложить ещё идею",  # ← исправлено
                                  callback_data="restart")]
        ]
    )

def mod_inline(card_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"approve:{card_id}:{user_id}")],  # ← исправлено
            [InlineKeyboardButton(text="✏️ Правки",    callback_data=f"edit:{card_id}:{user_id}")],    # ← исправлено
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{card_id}:{user_id}")]   # ← исправлено
        ]
    )

# ─────────────── 4.  ОБРАБОТЧИКИ ───────────────
@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    await m.answer(
        "👋 <b>Привет!</b>\n\n"
        "Здесь вы можете поделиться <b>идеей</b> или оставить <b>фидбек</b>.\n"
        "Нажмите кнопку ниже, чтобы начать.",
        reply_markup=begin_kb()
    )
    await state.set_state(Form.welcomed)

@dp.callback_query(F.data == "begin", Form.welcomed)
async def cb_begin(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("Что вы хотите отправить?", reply_markup=reply_kb)
    await state.set_state(Form.choosing)
    await cb.answer()

@dp.message(Form.choosing, F.text.in_(["💡 Идея", "📝 Фидбек"]))
async def choose_type(m: types.Message, state: FSMContext):
    tag = "IDEA" if "Идея" in m.text else "FEEDBACK"
    await state.update_data(tag=tag)
    await m.answer(
        "Пришлите сообщение одним отправлением.\n"
        "Это может быть текст, фото, видео, документ — что угодно.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(Form.writing)

@dp.message(Form.writing)
async def receive_any(m: types.Message, state: FSMContext):
    data = await state.get_data()
    tag  = data["tag"]

    media_types = {
        "photo", "video", "document", "audio",
        "animation", "video_note", "voice", "sticker"
    }
    if m.content_type in media_types:
        await bot.copy_message(
            chat_id=MODERATOR_CHAT_ID,
            from_chat_id=m.chat.id,
            message_id=m.message_id
        )

    meta_text = (
        f"<b>{tag}</b> от <a href='tg://user?id={m.from_user.id}'>{m.from_user.full_name}</a>\n\n"
        f"{m.caption or m.text or ''}"
    ).strip()

    card = await bot.send_message(
        MODERATOR_CHAT_ID,
        meta_text,
        reply_markup=mod_inline(0, m.from_user.id)   # временный id
    )
    await card.edit_reply_markup(reply_markup=mod_inline(card.message_id, m.from_user.id))
    MSG2USER[card.message_id] = m.from_user.id

    await m.answer(
        "Спасибо! Ваше сообщение передано на модерацию ✅",
        reply_markup=restart_kb()
    )
    await state.clear()

@dp.callback_query(F.data == "restart")
async def restart(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.answer("Что вы хотите отправить?", reply_markup=reply_kb)
    await state.set_state(Form.choosing)

@dp.callback_query(F.data.regexp(r"^(approve|edit|reject):"))
async def moderation_action(cb: types.CallbackQuery):
    action, card_id, user_id = cb.data.split(":")
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

    await cb.message.edit_reply_markup()
    await cb.answer("Готово!")

# ─────────────── 5.  ЗАПУСК ───────────────
async def main():
    logging.info("Bot is starting…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
