"""
Telegram UGC‑бот @ElectronUGCbot

Скелет бота на aiogram v3.
Функции:
• /start – приветствие + меню
• /idea – сбор текстовых историй
• /photo – сбор фото + подписи
• /status – личная статистика
• Модераторский чат с inline‑кнопками «✅ Одобрить / ✏️ Правки / ❌ Отклонить»
• /report – топ авторов (только для админов)

База: SQLite (можно поменять на PostgreSQL – заменить connection).
После деплоя: задайте переменные окружения BOT_TOKEN и ADMIN_CHAT_ID (через Railway/Heroku).
"""
import os
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (Message, CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram import html

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # ID модераторского чата

# --- DB ---
conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        tg_id INTEGER PRIMARY KEY,
        name TEXT,
        score INTEGER DEFAULT 0,
        joined TIMESTAMP
    );
    """
)
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER,
        type TEXT,
        content TEXT,
        file_id TEXT,
        status TEXT DEFAULT 'pending',
        ts TIMESTAMP
    );
    """
)
conn.commit()

# --- Bot / Dispatcher ---
logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()

def ensure_user(m: Message):
    cursor.execute("SELECT 1 FROM users WHERE tg_id=?", (m.from_user.id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (tg_id, name, joined) VALUES (?, ?, ?)",
            (m.from_user.id, m.from_user.full_name, datetime.utcnow()),
        )
        conn.commit()

# --- Keyboards ---
main_kb = (
    ReplyKeyboardBuilder()
    .add(*["/idea", "/photo", "/status"])
    .adjust(3)
    .as_markup(resize_keyboard=True)
)

def mod_kb(sub_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve:{sub_id}"),
                InlineKeyboardButton(text="✏️ Правки", callback_data=f"revise:{sub_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{sub_id}"),
            ]
        ]
    )

# --- Handlers ---
@router.message(Command("start"))
async def start_cmd(m: Message):
    ensure_user(m)
    await m.answer(
        "Привет! Это UGC‑бот <b>Электрон</b>\n\nВы можете:\n• отправить историю /idea\n• прислать фото /photo\n• посмотреть очки /status",
        reply_markup=main_kb,
    )

@router.message(Command("idea"))
async def idea_cmd(m: Message):
    ensure_user(m)
    await m.answer("Опишите вашу историю (до 1000 символов) одним сообщением.")
    dp.message.middleware.register(CollectTextMiddleware())

class CollectTextMiddleware:  # ждём первое следующее сообщение пользователя
    async def __call__(self, handler, event, data):
        m: Message = event
        if m.text and not m.text.startswith("/"):
            # сохраняем в БД
            cursor.execute(
                "INSERT INTO submissions (tg_id, type, content, ts) VALUES (?,?,?,?)",
                (m.from_user.id, "text", m.text[:1000], datetime.utcnow()),
            )
            sub_id = cursor.lastrowid
            conn.commit()
            await m.answer("Спасибо! История отправлена на модерацию.")
            # уведомляем админов
            await bot.send_message(
                ADMIN_CHAT_ID,
                f"<b>Новый текст от {html.quote(m.from_user.full_name)}</b>\n{sub_id}: {html.quote(m.text[:500])}",
                reply_markup=mod_kb(sub_id),
            )
            return  # stop propagation
        await handler(event, data)

@router.message(Command("photo"))
async def photo_cmd(m: Message):
    ensure_user(m)
    await m.answer("Пришлите одно фото с подписью (опционально).")

@router.message(F.photo)
async def handle_photo(m: Message):
    ensure_user(m)
    file_id = m.photo[-1].file_id
    caption = m.caption or ""
    cursor.execute(
        "INSERT INTO submissions (tg_id, type, content, file_id, ts) VALUES (?,?,?,?,?)",
        (m.from_user.id, "photo", caption[:500], file_id, datetime.utcnow()),
    )
    sub_id = cursor.lastrowid
    conn.commit()
    await m.answer("Фото получено и отправлено на модерацию.")
    await bot.send_photo(
        ADMIN_CHAT_ID,
        file_id,
        caption=f"<b>Новое фото от {html.quote(m.from_user.full_name)}</b>\n{sub_id}: {html.quote(caption)}",
        reply_markup=mod_kb(sub_id),
    )

@router.message(Command("status"))
async def status_cmd(m: Message):
    ensure_user(m)
    cursor.execute("SELECT score FROM users WHERE tg_id=?", (m.from_user.id,))
    score = cursor.fetchone()[0]
    await m.answer(f"У вас <b>{score}</b> баллов. Спасибо за вклад!")

# --- Admin callbacks ---
@router.callback_query(F.data.startswith(tuple(["approve", "reject", "revise"])))
async def callbacks(cb: CallbackQuery):
    action, sub_id = cb.data.split(":")
    sub_id = int(sub_id)
    cursor.execute("SELECT tg_id, type FROM submissions WHERE id=?", (sub_id,))
    row = cursor.fetchone()
    if not row:
        await cb.answer("Уже обработано")
        return
    user_id, sub_type = row
    if action == "approve":
        cursor.execute("UPDATE submissions SET status='approved' WHERE id=?", (sub_id,))
        cursor.execute("UPDATE users SET score = score + 5 WHERE tg_id=?", (user_id,))
        conn.commit()
        await bot.send_message(user_id, "🎉 Ваш материал одобрен и скоро выйдет в канале!")
        await cb.message.edit_text(cb.message.html_text + "\n✅ Одобрено")
    elif action == "reject":
        cursor.execute("UPDATE submissions SET status='rejected' WHERE id=?", (sub_id,))
        conn.commit()
        await bot.send_message(user_id, "К сожалению, материал отклонён. Попробуйте снова :)")
        await cb.message.edit_text(cb.message.html_text + "\n❌ Отклонено")
    elif action == "revise":
        cursor.execute("UPDATE submissions SET status='needs_edit' WHERE id=?", (sub_id,))
        conn.commit()
        await bot.send_message(user_id, "✏️ Модератор просит внести правки. Отправьте новую версию /idea или /photo.")
        await cb.message.edit_text(cb.message.html_text + "\n✏️ Нужны правки")
    await cb.answer("Готово")

# --- /report (admins only) ---
@router.message(Command("report"))
async def report_cmd(m: Message):
    if m.chat.id != ADMIN_CHAT_ID:
        return
    cursor.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
    rows = cursor.fetchall()
    msg = "<b>TOP‑10 авторов</b>\n" + "\n".join([f"{i+1}. {html.quote(n)} — {s} баллов" for i, (n, s) in enumerate(rows)])
    await m.answer(msg)

# --- register & run ---
dp.include_router(router)

def main():
    dp.run_polling(bot)

if __name__ == "__main__":
    main()
