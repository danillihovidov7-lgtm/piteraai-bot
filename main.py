import asyncio
import logging
import requests
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncpg

# ================= НАСТРОЙКИ =================
TOKEN = "8227205098:AAG4rcBsPA2beVeuaunTUwfB_WJx6gOQgmE"
GROQ_API_KEY = "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"
DATABASE_URL = "postgresql://postgres:JLiHVxsNGInOITXeaGnsXWiTpBPYAkvy@reseau.proxy.rlwy.net:34240/railway"

# Ссылки на оплату
PAY_290 = "https://example.com/pay/290"  # 1 месяц
PAY_590 = "https://example.com/pay/590"  # 3 месяца
PAY_890 = "https://example.com/pay/890"  # 6 месяцев

bot = Bot(token=TOKEN)
dp = Dispatcher()

pool = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        await conn.execute('''CREATE TABLE IF NOT EXISTS users
                              (
                                  user_id
                                  BIGINT
                                  PRIMARY
                                  KEY,
                                  username
                                  TEXT,
                                  daily_requests
                                  INTEGER
                                  DEFAULT
                                  0,
                                  last_reset
                                  TEXT,
                                  subscription
                                  TEXT
                                  DEFAULT
                                  'free',
                                  sub_end
                                  TEXT
                              )''')

        await conn.execute('''CREATE TABLE IF NOT EXISTS messages
                              (
                                  id
                                  SERIAL
                                  PRIMARY
                                  KEY,
                                  user_id
                                  BIGINT,
                                  role
                                  TEXT,
                                  content
                                  TEXT,
                                  timestamp
                                  TEXT
                              )''')


# ===================== ЧЕЛОВЕЧЕСКИЙ ПРОМПТ =====================
SYSTEM_PROMPT = """Ты — обычный парень из Беларуси, 27 лет, зовут Питер. 
Разговариваешь живо, естественно, с лёгким современным сленгом. 
Иногда используешь мат, но не через слово. 
Отвечаешь как в реальной переписке: коротко, по делу, с эмоциями. 
Не пишешь "как ИИ", "я могу помочь", "вот что я думаю" и прочий роботский текст. 
Будь живым, иногда ироничным, иногда прямолинейным, иногда злись, показывай эмоции и самое главное."""


# ===================== ФУНКЦИИ =====================
async def save_message(user_id, role, content):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (user_id, role, content, timestamp) VALUES ($1, $2, $3, $4)",
            user_id, role, content, datetime.now().isoformat()
        )


async def get_history(user_id, limit=12):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM messages WHERE user_id = $1 ORDER BY id ASC LIMIT $2",
            user_id, limit
        )
        return [{"role": r['role'], "content": r['content']} for r in rows]


def get_main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Генерация", callback_data="generate")],
        [InlineKeyboardButton(text="Контент-план", callback_data="plan")],
        [InlineKeyboardButton(text="Подписка", callback_data="subscription")]
    ])
    return kb


@dp.message(Command("start"))
async def start(message: types.Message):
    sub, remaining = get_user_status(message.from_user.id)
    status = "✅ Pro" if sub != 'free' else "🔓 Бесплатно"

    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"Статус: <b>{status}</b>\n"
        f"Запросов сегодня: <b>{remaining}/10</b>\n\n"
        "Что будем делать?",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    await callback.answer()
    if callback.data == "subscription":
        sub, remaining = get_user_status(callback.from_user.id)

        status_text = "✅ <b>Подписка активна</b>" if sub != 'free' else "🔓 <b>Бесплатный тариф</b>"

        text = f"""<b>🎯 PiteraAI — Подписка</b>

{status_text}

<b>Тарифы:</b>

💎 <b>290 ₽</b> — 1 месяц
• Без ограничений по запросам
• Приоритетные ответы
• Память диалогов

🔥 <b>590 ₽</b> — 3 месяца (-15%)
• Всё из тарифа 1 месяц
• Экономия 105 ₽

🚀 <b>890 ₽</b> — 6 месяцев (-35%)
• Максимальная выгода
• Экономия 460 ₽
• Самый выгодный вариант

Выбери подходящий тариф 👇"""

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 290 ₽ — 1 месяц", url=PAY_290)],
            [InlineKeyboardButton(text="🔥 590 ₽ — 3 месяца", url=PAY_590)],
            [InlineKeyboardButton(text="🚀 890 ₽ — 6 месяцев", url=PAY_890)]
        ])

        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        return


# Обработка любых сообщений о подписке
@dp.message()
async def handle_message(message: types.Message):
    text = message.text.lower() if message.text else ""

    # Если человек спрашивает про подписку — показываем кнопки
    if any(word in text for word in ["подпис", "тариф", "сколько стоит", "цена", "платн", "pro", "премиум"]):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="290 ₽ — 1 месяц", url=PAY_290)],
            [InlineKeyboardButton(text="590 ₽ — 3 месяца", url=PAY_590)],
            [InlineKeyboardButton(text="890 ₽ — 6 месяцев", url=PAY_890)]
        ])
        await message.answer("Вот актуальные тарифы:", reply_markup=kb)
        return

    # Обычная обработка сообщений (для всего остального)
    if not message.text or len(message.text.strip()) < 2:
        return

    await bot.send_chat_action(message.chat.id, "typing")

    # Получаем историю
    history = await get_history(message.from_user.id)
    messages = history + [{"role": "user", "content": message.text}]

    await save_message(message.from_user.id, "user", message.text)

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                "temperature": 0.85,
                "max_tokens": 1200
            },
            timeout=50
        )
        response.raise_for_status()
        result = response.json()
        answer = result['choices'][0]['message']['content']

        await message.answer(answer)
        await save_message(message.from_user.id, "assistant", answer)

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer("Не понял, повтори ещё раз.")


async def main():
    await init_db()
    logging.basicConfig(level=logging.INFO)
    print("🚀 PiteraAI запущен (человеческий стиль + память)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
