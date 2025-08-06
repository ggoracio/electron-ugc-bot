import os
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
    DefaultBotProperties,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramForbiddenError, TelegramMigrateToChat
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import asyncio
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    BotCommand,  # остальные нужные вам классы
    ParseMode,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# …

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)  # здесь указываем default
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN     = os.getenv("BOT_TOKEN")
MOD_CHAT_ID   = int(os.getenv("MOD_CHAT_ID"))  # -100xxxxx (super‑group!)

if not BOT_TOKEN or not MOD_CHAT_ID:
    raise RuntimeError("Set BOT_TOKEN and MOD_CHAT_ID in env vars!")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp  = Dispatcher()

# ──────────────── FSM ────────────────
class Form(StatesGroup):
    waiting_tag   = State()
    waiting_text  = State()

# ──────────────── Keyboards ────────────────
def start_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="💡 Предложить идею",     callback_data="idea"  )],
        [InlineKeyboardButton(text="✉️ Оставить фидбек",    callback_data="feedback")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

restart_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="🚀 Отправить ещё", callback_data="restart")]]
)

mod_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять",  callback_data="approve"),
            InlineKeyboardButton(text="✏️ Правки",   callback_data="edit"   ),
            InlineKeyboardButton(text="❌ Отклонить", callback_data="decline"),
        ]
    ]
)

# ──────────────── Start ────────────────
@dp.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(
        "<b>Привет!</b>\nВыберите действие:",
        reply_markup=start_kb()
    )

# ──────────────── Choosing tag ────────────────
@dp.callback_query(F.data.in_("idea feedback"))
async def choose_type(c: CallbackQuery, state: FSMContext):
    tag = "#idea" if c.data == "idea" else "#feedback"
    await state.update_data(tag=tag)
    await c.message.edit_text("Отправьте текст сообщения, я перешлю его модератору ✉️")
    await state.set_state(Form.waiting_text)
    await c.answer()

# ──────────────── Receiving text from user ────────────────
@dp.message(Form.waiting_text)
async def receive_text(m: Message, state: FSMContext):
    data = await state.get_data()
    tag  = data.get("tag", "#idea")

    txt  = f"{tag}\n<b>От \u200b</b><a href=\"tg://user?id={m.from_user.id}\">{m.from_user.full_name}</a>:\n\n{m.html_text}"

    # пытаемся переслать модераторам, учитываем возможную миграцию чата
    global MOD_CHAT_ID
    try:
        sent = await bot.send_message(MOD_CHAT_ID, txt, reply_markup=mod_buttons)
    except TelegramMigrateToChat as e:
        MOD_CHAT_ID = e.migrate_to_chat_id
        sent = await bot.send_message(MOD_CHAT_ID, txt, reply_markup=mod_buttons)
    except TelegramForbiddenError:
        await m.answer("Ошибка: бот не может писать в модераторский чат. Добавьте его как администратора.")
        return

    # сохраняем id исходного сообщения, чтобы вернуть результат
    await state.update_data(user_msg_id=m.message_id, mod_msg_id=sent.message_id)
    await m.answer("Спасибо! Сообщение передано модератору. Ожидайте решения…", reply_markup=restart_kb)
    await state.clear()

# ──────────────── Buttons в мод‑чате ────────────────
@dp.callback_query(F.data.in_("approve decline edit"))
async def moderation_action(c: CallbackQuery):
    # вытягиваем id пользователя и его исходного сообщения из текста
    if not c.message or not c.message.text:
        return await c.answer("Нет текста", show_alert=True)

    lines = c.message.text.split("\n", 2)
    if len(lines) < 2:
        return await c.answer("Формат неизвестен", show_alert=True)

    first_line = lines[1]  # «От …»
    try:
        user_id = int(first_line.split("id=")[1].split("\">")[0])
    except Exception:
        return await c.answer("Не смог узнать пользователя", show_alert=True)

    verdict = c.data
    text_for_user = {
        "approve":  "✅ Ваша идея принята! Спасибо ✨",
        "decline":  "❌ К сожалению, идея не подходит. Но мы ждём другие!",
        "edit":     "✏️ Спасибо! Мы прочли вашу идею и свяжемся при необходимости.",
    }[verdict]

    try:
        await bot.send_message(user_id, text_for_user, reply_markup=restart_kb)
    except TelegramForbiddenError:
        pass  # пользователь закрыл диалог

    # пометим сообщение в мод‑чате
    tag = {"approve": "✅", "decline": "❌", "edit": "✏️"}[verdict]
    await c.message.edit_text(f"{tag} {c.message.text}")
    await c.answer("Готово")

# ──────────────── restart кнопка ────────────────
@dp.callback_query(F.data == "restart")
async def restart_flow(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()  # уберём кнопку «Отправить ещё»
    await c.message.answer("Выберите действие:", reply_markup=start_kb())
    await c.answer()

# ──────────────── main ────────────────
async def main():
    logging.info("Bot is starting…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


