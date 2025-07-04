import os
import logging
import asyncio
import asyncpg
import databases
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Update,
    Message,
    CallbackQuery,
    FSInputFile,
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

# ——— Текстовый прогноз (глобально) ———
TEXT_FORECAST: str = ""

# ——— Подключение к базе данных PostgreSQL ———
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://username:password@localhost/dbname")  # Замените на ваши данные
database = databases.Database(DATABASE_URL)

# Aliases для удобства
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

# ——— Конфигурация ———
BOT_TOKEN    = os.getenv("BOT_TOKEN",    "8094761598:AAFDmaV_qAKTim2YnkuN8ksQFvwNxds7HLQ")
ADMIN_ID     = int(os.getenv("ADMIN_ID", "6688088575"))
CATEGORIES   = ['football', 'hockey', 'dota', 'cs', 'tennis']
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://ai-telegram-bot1.onrender.com")
WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL  = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT         = int(os.getenv("PORT", "10000"))

# ——— Логирование ———
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ——— Инициализация бота и диспетчера ———
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp  = Dispatcher(storage=MemoryStorage())

# ——— FSM-состояния ———
class UploadState(StatesGroup):
    waiting_photo    = State()
    waiting_category = State()
    waiting_text     = State()  # Добавлено для загрузки текста

# ——— Клавиатуры ———
def generate_categories_keyboard(user_forecasts: dict) -> InlineKeyboardMarkup:
    emoji_map = {
        'football': '⚽️',
        'hockey'  : '🏒',
        'dota'    : '🎮',
        'cs'      : '🔫',
        'tennis'  : '🎾',
    }
    kb = []
    for sport in CATEGORIES:
        count = len(user_forecasts.get(sport, []))
        cb = f"buy_{sport}" if count else "none"
        label = f"{emoji_map[sport]} {sport.capitalize()} — {count}"
        kb.append([{"text": label, "callback_data": cb}])
    return InlineKeyboardMarkup.model_validate({"inline_keyboard": kb})

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [{"text": "📤 Загрузить прогноз", "callback_data": "admin_upload"}],
        [{"text": "📊 Просмотр прогнозов", "callback_data": "admin_view"}],
        [{"text": "🗑 Очистить прогнозы", "callback_data": "admin_clear"}],
        [{"text": "📝 Загрузить текстом", "callback_data": "admin_upload_text"}],  # Новая кнопка
        [{"text": "🔙 Назад", "callback_data": "back_to_start"}],
    ]
    return InlineKeyboardMarkup.model_validate({"inline_keyboard": kb})

def bottom_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    kb = [[{"text": "🔮 AI прогнозы"}]]
    if user_id == ADMIN_ID:
        kb.append([{"text": "Админ"}])
    kb.append([{"text": "📝 Прогнозы текстом"}])  # Добавлена кнопка для текстовых прогнозов
    return ReplyKeyboardMarkup.model_validate({
        "keyboard": kb,
        "resize_keyboard": True
    })

# ——— Подключение к базе данных (PostgreSQL) ———
async def connect_db():
    await database.connect()
    logger.info("Подключение к базе данных установлено.")

async def disconnect_db():
    await database.disconnect()
    logger.info("Подключение к базе данных закрыто.")

# ——— Создание таблицы прогнозов ———
async def create_forecasts_table():
    query = """
    CREATE TABLE IF NOT EXISTS forecasts (
        id SERIAL PRIMARY KEY,
        sport VARCHAR(50) NOT NULL,
        file_name VARCHAR(255) NOT NULL,
        file_path TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    await database.execute(query)

# ——— Загрузка прогноза в базу данных ———
async def save_forecast_to_db(sport: str, file_name: str, file_path: str):
    query = """
    INSERT INTO forecasts (sport, file_name, file_path)
    VALUES (:sport, :file_name, :file_path)
    """
    await database.execute(query, values={"sport": sport, "file_name": file_name, "file_path": file_path})

# ——— Загрузка прогнозов из базы данных ———
async def get_forecasts_from_db():
    query = "SELECT sport, file_name, file_path FROM forecasts"
    return await database.fetch_all(query)

# ——— /start ———
@dp.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("intro_done"):
        await bot.send_chat_action(message.chat.id, action="upload_video")
        await message.answer_video(
            video="BAACAgIAAxkBAAIBCGhdn70oSM1KnFvcGOvOjuQ50P2TAAJ4gAACKGXwSjSGuqbploX4NgQ",
            caption=( 
                "🎥 <b>По тенденции развития проекта</b>, в будущем будет выпущено качественное <b>реалистичное видео от AI</b>\n"
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
        # Кнопка "🔮 AI прогнозы"
        ikm = InlineKeyboardMarkup.model_validate({
            "inline_keyboard": [
                [{"text": "🔮 AI прогнозы", "callback_data": "start_predictions"}]
            ]
        })
        await message.answer("Нажмите, чтобы перейти в раздел прогнозов:", reply_markup=ikm)
        await state.update_data(intro_done=True)
        return

    await full_start(message, state)

# ——— Inline "AI прогнозы" ———
@dp.callback_query(F.data == "start_predictions")
async def handle_intro_button(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await full_start(callback.message, state)

# ——— Получение прогнозов из базы данных ———
async def full_start(message: Message, state: FSMContext):
    data = await state.get_data()
    user_forecasts = await get_forecasts_from_db()

    # Преобразуем данные для отображения в клавиатуре
    forecasts = {}
    for sport in CATEGORIES:
        forecasts[sport] = []
    for forecast in user_forecasts:
        forecasts[forecast["sport"]].append(forecast)

    await message.answer("Выбери категорию спорта для получения прогноза:",
                         reply_markup=generate_categories_keyboard(forecasts))
    await message.answer("🦅", reply_markup=bottom_keyboard(message.from_user.id))

# Загрузка прогноза в базу данных и на диск
@dp.message(F.photo, StateFilter(UploadState.waiting_photo))
async def handle_photo_upload(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(UploadState.waiting_category)
    kb = [
        [{"text": s.capitalize(), "callback_data": f"save_to_{s}"}]
        for s in CATEGORIES
    ]
    ikm = InlineKeyboardMarkup.model_validate({"inline_keyboard": kb})
    await message.answer("Выберите категорию для сохранения:", reply_markup=ikm)

@dp.callback_query(F.data.startswith("save_to_"), StateFilter(UploadState.waiting_category))
async def save_to_category(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo_id = data.get("photo_id")
    sport = callback.data.replace("save_to_", "")
    folder = f"forecasts/{sport}"
    os.makedirs(folder, exist_ok=True)
    files = [f for f in os.listdir(folder) if f.lower().endswith((".png","jpg","jpeg"))]
    file_name = f"{len(files)+1}.jpg"
    file = await bot.get_file(photo_id)
    await bot.download_file(file.file_path, os.path.join(folder, file_name))

    # Сохраняем прогноз в базу данных
    file_path = os.path.join(folder, file_name)
    await save_forecast_to_db(sport, file_name, file_path)
    
    await callback.answer()
    await callback.message.answer(f"✅ Прогноз сохранён в категорию {sport.capitalize()}")
    await state.clear()

# ——— Fallback ———
@dp.message()
async def general_handler(message: Message):
    logger.info(f"Получено сообщение {message.message_id} от {message.from_user.id}")
    await message.answer("Я получил ваше сообщение! ✅")

# ——— Webhook ———
async def on_start(request):
    return web.Response(text="Bot is running")

async def on_webhook(request):
    data = await request.json()
    update = Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

async def on_app_startup(app):
    info = await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set: {info}")

app = web.Application()
app.add_routes([ 
    web.post(WEBHOOK_PATH, on_webhook),
    web.get("/", on_start),
])
app.on_startup.append(on_app_startup)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)

