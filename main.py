import os
import logging
import databases
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Update, Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

# ────────────────────────────────────────────────────────────
#   Глобальный текстовый прогноз
# ────────────────────────────────────────────────────────────
TEXT_FORECAST: str = ""

# ────────────────────────────────────────────────────────────
#   PostgreSQL
# ────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:pass@localhost/dbname"    # замените или вынесите в переменные окружения
)
database = databases.Database(DATABASE_URL)

# ────────────────────────────────────────────────────────────
#   Конфигурация бота
# ────────────────────────────────────────────────────────────
BOT_TOKEN    = os.getenv("BOT_TOKEN",    "8094761598:AAFDmaV_qAKTim2YnkuN8ksQFvwNxds7HLQ")
ADMIN_ID     = int(os.getenv("ADMIN_ID", "6688088575"))
CATEGORIES   = ['football', 'hockey', 'dota', 'cs', 'tennis']
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://ai-telegram-bot1.onrender.com")
WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL  = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT         = int(os.getenv("PORT", "10000"))

# ────────────────────────────────────────────────────────────
#   Логирование
# ────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
#   Инициализация бота
# ────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp  = Dispatcher(storage=MemoryStorage())

# ────────────────────────────────────────────────────────────
#   FSM-состояния
# ────────────────────────────────────────────────────────────
class UploadState(StatesGroup):
    waiting_photo    = State()
    waiting_category = State()
    waiting_text     = State()

# ────────────────────────────────────────────────────────────
#   БД: пересоздание таблиц (вызывается один раз при запуске)
# ────────────────────────────────────────────────────────────
async def recreate_tables() -> None:
    await database.execute("DROP TABLE IF EXISTS deliveries;")
    await database.execute("DROP TABLE IF EXISTS forecasts;")
    await database.execute("DROP TABLE IF EXISTS users;")

    await database.execute("""
    CREATE TABLE forecasts (
        id         SERIAL PRIMARY KEY,
        sport      VARCHAR(50) NOT NULL,
        file_name  VARCHAR(255) NOT NULL,
        file_path  TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    await database.execute("""
    CREATE TABLE deliveries (
        id          SERIAL PRIMARY KEY,
        user_id     BIGINT NOT NULL,
        forecast_id INT NOT NULL REFERENCES forecasts(id) ON DELETE CASCADE,
        UNIQUE(user_id, forecast_id)
    );
    """)

    await database.execute("""
    CREATE TABLE users (
        user_id    BIGINT PRIMARY KEY,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

# ────────────────────────────────────────────────────────────
#   Утилиты работы с прогнозами
# ────────────────────────────────────────────────────────────
async def save_forecast_to_db(sport: str, file_name: str, file_path: str):
    await database.execute(
        "INSERT INTO forecasts (sport, file_name, file_path) "
        "VALUES (:s, :f, :p)",
        values={"s": sport, "f": file_name, "p": file_path}
    )

async def get_available_forecasts(user_id: int) -> dict[str, list[str]]:
    rows = await database.fetch_all("""
        SELECT f.sport, f.file_name
        FROM forecasts f
        LEFT JOIN deliveries d
          ON d.forecast_id = f.id AND d.user_id = :uid
        WHERE d.forecast_id IS NULL
    """, values={"uid": user_id})

    res = {s: [] for s in CATEGORIES}
    for r in rows:
        res[r["sport"]].append(r["file_name"])
    return res

async def mark_delivered(user_id: int, sport: str, file_name: str):
    fid = await database.fetch_val(
        "SELECT id FROM forecasts WHERE sport=:s AND file_name=:f",
        values={"s": sport, "f": file_name}
    )
    if fid:
        await database.execute(
            "INSERT INTO deliveries (user_id, forecast_id) "
            "VALUES (:u,:f) ON CONFLICT DO NOTHING",
            values={"u": user_id, "f": fid}
        )

# ────────────────────────────────────────────────────────────
#   Утилиты отслеживания пользователей
# ────────────────────────────────────────────────────────────
async def track_user(user_id: int):
    exists = await database.fetch_val(
        "SELECT 1 FROM users WHERE user_id = :uid",
        values={"uid": user_id}
    )
    if not exists:
        await database.execute(
            "INSERT INTO users (user_id) VALUES (:uid)",
            values={"uid": user_id}
        )
    else:
        await database.execute(
            "UPDATE users SET last_seen = NOW() WHERE user_id = :uid",
            values={"uid": user_id}
        )

async def get_daily_users_count() -> int:
    return await database.fetch_val(
        "SELECT COUNT(*) FROM users WHERE last_seen::date = CURRENT_DATE"
    ) or 0

# ────────────────────────────────────────────────────────────
#   Клавиатуры
# ────────────────────────────────────────────────────────────
def generate_categories_keyboard(user_forecasts: dict) -> InlineKeyboardMarkup:
    kb = []
    for sport in CATEGORIES:
        count = len(user_forecasts.get(sport, []))
        cb = f"buy_{sport}" if count else "none"
        kb.append([{"text": f"{sport.capitalize()} — {count}", "callback_data": cb}])
    return InlineKeyboardMarkup.model_validate({"inline_keyboard": kb})

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [{"text": "📤 Загрузить прогноз", "callback_data": "admin_upload"}],
        [{"text": "📊 Просмотр прогнозов", "callback_data": "admin_view"}],
        [{"text": "🗑 Очистить прогнозы", "callback_data": "admin_clear"}],
        [{"text": "📝 Загрузить текстом", "callback_data": "admin_upload_text"}],
        [{"text": "📅 Пользователи сегодня", "callback_data": "admin_users_today"}],  # ← новая кнопка
        [{"text": "🔙 Назад", "callback_data": "back_to_start"}],
    ]
    return InlineKeyboardMarkup.model_validate({"inline_keyboard": kb})

def bottom_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    kb = [[{"text": "🔮 AI прогнозы"}]]
    if user_id == ADMIN_ID:
        kb.append([{"text": "Админ"}])
    kb.append([{"text": "📝 Прогнозы текстом"}])
    return ReplyKeyboardMarkup.model_validate({"keyboard": kb, "resize_keyboard": True})

# ────────────────────────────────────────────────────────────
#   /start
# ────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await track_user(message.from_user.id)        # → отмечаем визит
    data = await state.get_data()

    if not data.get("intro_done"):
        await bot.send_chat_action(message.chat.id, action="upload_video")
        await message.answer_video(
            video="BAACAgIAAxkBAAIBCGhdn70oSM1KnFvcGOvOjuQ50P2TAAJ4gAACKGXwSjSGuqbploX4NgQ",
            caption=(
                "🎥 <b>По тенденции развития проекта</b>, в будущем будет выпущено "
                "качественное <b>реалистичное видео от AI</b>\n"
                "📊 <b>На момент создания:</b> 71% побед, средний кэф — 1.78\n"
                "🧠 <b>Прогнозы формируются на базе AI</b>, ежедневно в 07:00\n"
                "👇 <b>Жми кнопку «Прогнозы AI» и получи свой первый прогноз</b>"
            )
        )
        await message.answer(
            "💡 <b>В прошлом уже был успешный проект с AI-вилками</b>, но он был закрыт\n"
            "🔐 <b>Количество участников</b> будет ограничено\n"
            "📉 <b>Прибыль текущая:</b> стабильная, цель: рост процента побед\n\n"
            "⚙️ <b>Сейчас</b>: AI сканирует источники, анализирует коэффициенты\n"
            "🚀 <b>В будущем</b>: интерактивная аналитика, новые функции"
        )
        ikm = InlineKeyboardMarkup.model_validate({
            "inline_keyboard": [
                [{"text": "🔮 AI прогнозы", "callback_data": "start_predictions"}]
            ]
        })
        await message.answer("Нажмите, чтобы перейти в раздел прогнозов:", reply_markup=ikm)
        await state.update_data(intro_done=True)
        return

    await full_start(message, state)

# ────────────────────────────────────────────────────────────
#   Кнопка из intro-месседжа
# ────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "start_predictions")
async def handle_intro_button(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await full_start(callback.message, state)

# ────────────────────────────────────────────────────────────
#   Reply "🔮 AI прогнозы"
# ────────────────────────────────────────────────────────────
@dp.message(F.text == "🔮 AI прогнозы")
async def bottom_start(message: Message, state: FSMContext):
    await full_start(message, state)

# ────────────────────────────────────────────────────────────
#   Показ категорий (из БД)
# ────────────────────────────────────────────────────────────
async def full_start(message: Message, state: FSMContext):
    await track_user(message.from_user.id)        # → отмечаем визит
    user_forecasts = await get_available_forecasts(message.from_user.id)
    await state.update_data(user_forecasts=user_forecasts)
    await message.answer(
        "Выбери категорию спорта для получения прогноза:",
        reply_markup=generate_categories_keyboard(user_forecasts)
    )
    await message.answer("🦅", reply_markup=bottom_keyboard(message.from_user.id))

# ────────────────────────────────────────────────────────────
#   Админ-панель
# ────────────────────────────────────────────────────────────
@dp.message(F.text == "Админ")
async def admin_menu_handler(message: Message):
    await message.answer("Выберите действие:", reply_markup=admin_menu_keyboard())

@dp.callback_query(F.data == "admin_users_today")
async def admin_users_today(callback: CallbackQuery):
    count = await get_daily_users_count()
    await callback.message.answer(f"👥 Пользователей за сегодня: <b>{count}</b>")
    await callback.answer()

# ────────────────────────────────────────────────────────────
#   Остальные admin callback’ы (upload / view / clear / text)
# ────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "admin_upload")
async def admin_upload(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📤 Загрузка прогнозов…\nОтправьте фото для загрузки.")
    await state.set_state(UploadState.waiting_photo)

@dp.callback_query(F.data == "admin_view")
async def admin_view(callback: CallbackQuery):
    rows = await database.fetch_all("SELECT sport, COUNT(*) AS c FROM forecasts GROUP BY sport")
    rep = "\n".join(f"{r['sport'].capitalize()}: {r['c']}" for r in rows) or "Пусто"
    await callback.message.answer(f"📊 В базе:\n{rep}")
    await callback.answer()

@dp.callback_query(F.data == "admin_clear")
async def admin_clear(callback: CallbackQuery):
    global TEXT_FORECAST
    TEXT_FORECAST = ""
    await database.execute("TRUNCATE deliveries, forecasts RESTART IDENTITY CASCADE")
    for sport in CATEGORIES:
        folder = f"forecasts/{sport}"
        if os.path.exists(folder):
            for f in os.listdir(folder):
                os.remove(os.path.join(folder, f))
    await callback.message.answer("🗑 Всё очищено.")
    await callback.answer()

@dp.callback_query(F.data == "admin_upload_text")
async def admin_upload_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Отправьте текст прогнозов:")
    await state.set_state(UploadState.waiting_text)

# ────────────────────────────────────────────────────────────
#   Загрузка текста
# ────────────────────────────────────────────────────────────
@dp.message(StateFilter(UploadState.waiting_text))
async def handle_text_upload(message: Message, state: FSMContext):
    global TEXT_FORECAST
    TEXT_FORECAST = message.text
    await message.answer("Текстовый прогноз сохранён!")
    await state.clear()

# ────────────────────────────────────────────────────────────
#   Загрузка фото
# ────────────────────────────────────────────────────────────
@dp.message(F.photo, StateFilter(UploadState.waiting_photo))
async def handle_photo_upload(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(UploadState.waiting_category)
    ikm = InlineKeyboardMarkup.model_validate({
        "inline_keyboard": [
            [{"text": s.capitalize(), "callback_data": f"save_to_{s}"}] for s in CATEGORIES
        ]
    })
    await message.answer("Выберите категорию для сохранения:", reply_markup=ikm)

@dp.callback_query(F.data.startswith("save_to_"), StateFilter(UploadState.waiting_category))
async def save_to_category(callback: CallbackQuery, state: FSMContext):
    data   = await state.get_data()
    sport  = callback.data.replace("save_to_", "")
    folder = f"forecasts/{sport}"
    os.makedirs(folder, exist_ok=True)
    fname  = f"{len(os.listdir(folder)) + 1}.jpg"
    file   = await bot.get_file(data["photo_id"])
    await bot.download_file(file.file_path, os.path.join(folder, fname))
    await save_forecast_to_db(sport, fname, os.path.join(folder, fname))
    await callback.message.answer(f"✅ Прогноз сохранён в категорию {sport.capitalize()}")
    await state.clear()
    await callback.answer()

# ────────────────────────────────────────────────────────────
#   Покупка прогноза
# ────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("buy_"))
async def buy_handler(callback: CallbackQuery, state: FSMContext):
    data  = await state.get_data()
    sport = callback.data.replace("buy_", "")
    files = data.get("user_forecasts", {}).get(sport, [])
    if not files:
        await callback.answer("Прогнозов нет 😞", show_alert=True)
        return

    fname = files.pop(0)
    photo = FSInputFile(os.path.join(f"forecasts/{sport}", fname))
    await callback.message.answer_photo(photo, caption=sport.capitalize())
    await mark_delivered(callback.from_user.id, sport, fname)
    await state.update_data(user_forecasts=data["user_forecasts"])
    await callback.message.edit_reply_markup(
        reply_markup=generate_categories_keyboard(data["user_forecasts"])
    )
    await callback.answer()

# ────────────────────────────────────────────────────────────
#   Текстовые прогнозы
# ────────────────────────────────────────────────────────────
@dp.message(F.text == "📝 Прогнозы текстом")
async def show_text_forecast(message: Message):
    await message.answer(TEXT_FORECAST or "Текстовых прогнозов нет 😞")

# ────────────────────────────────────────────────────────────
#   Fallback-хэндлер
# ────────────────────────────────────────────────────────────
@dp.message()
async def general_handler(message: Message):
    await track_user(message.from_user.id)        # → отмечаем визит даже при «лишних» сообщениях
    await message.answer("Я получил ваше сообщение! ✅")

# ────────────────────────────────────────────────────────────
#   Webhook
# ────────────────────────────────────────────────────────────
async def on_start(request):
    return web.Response(text="Bot is running")

async def on_webhook(request):
    await dp.feed_update(bot, Update(**await request.json()))
    return web.Response()

async def on_app_startup(app):
    await database.connect()
    await recreate_tables()                       # пересоздаём таблицы (при желании замените на миграции)
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook set")

app = web.Application()
app.add_routes([web.post(WEBHOOK_PATH, on_webhook), web.get("/", on_start)])
app.on_startup.append(on_app_startup)
app.on_cleanup.append(lambda _app: database.disconnect())

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
