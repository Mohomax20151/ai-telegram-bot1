import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    Message, KeyboardButton, ReplyKeyboardMarkup, CallbackQuery, ContentType
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

# ——— Конфигурация ———
BOT_TOKEN   = os.getenv("BOT_TOKEN", "8094761598:AAFDmaV_qAKTim2YnkuN8ksQFvwNxds7HLQ")
ADMIN_ID    = int(os.getenv("ADMIN_ID", "6688088575"))
CATEGORIES  = ['football', 'hockey', 'dota', 'cs', 'tennis']
WEBHOOK_HOST= os.getenv("WEBHOOK_HOST", "https://ai-telegram-bot1.onrender.com")
WEBHOOK_PATH= f"/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT        = int(os.getenv("PORT", "10000"))

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

class IntroState(StatesGroup):
    intro_shown = State()

# ——— Клавиатуры ———
def generate_categories_keyboard(user_forecasts: dict) -> InlineKeyboardMarkup:
    kb = []
    for sport in CATEGORIES:
        count = len(user_forecasts.get(sport, []))
        cb = f"buy_{sport}" if count else "none"
        kb.append([InlineKeyboardButton(f"{sport.capitalize()} — {count}", callback_data=cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("📤 Загрузить прогноз", callback_data="admin_upload")],
        [InlineKeyboardButton("📊 Просмотр прогнозов", callback_data="admin_view")],
        [InlineKeyboardButton("🗑 Очистить прогнозы", callback_data="admin_clear")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")],
    ])

def bottom_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton("🔮 AI прогнозы")]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("Админ")])  # Кнопка "Админ"
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ——— Обработчик /start ———
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
        await message.answer(
            "Нажмите, чтобы перейти в раздел прогнозов:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton("🔮 AI прогнозы", callback_data="start_predictions")]]
            )
        )
        await state.update_data(intro_done=True)
        return
    await full_start(message, state)

# ——— Полный старт (после интро) ———
async def full_start(message: Message, state: FSMContext):
    data = await state.get_data()
    user_forecasts = data.get("user_forecasts")
    if user_forecasts is None:
        user_forecasts = {}
        for sport in CATEGORIES:
            folder = f"forecasts/{sport}"
            try:
                files = [f for f in os.listdir(folder) if f.lower().endswith((".png","jpg","jpeg"))]
            except FileNotFoundError:
                files = []
            user_forecasts[sport] = files
        await state.update_data(user_forecasts=user_forecasts)

    await message.answer(
        "Выбери категорию спорта для получения прогноза:",
        reply_markup=generate_categories_keyboard(user_forecasts)
    )
    await message.answer("🦅", reply_markup=bottom_keyboard(message.from_user.id))

# ——— Обработчик нажатия кнопки «Админ» ———
@dp.message(lambda m: m.text == "Админ")
async def admin_menu_handler(message: Message):
    logger.info(f"Запрошено админ-меню пользователем {message.from_user.id}")
    await message.answer("Выберите действие:", reply_markup=admin_menu_keyboard())

# ——— Обработчик callback’ов админского меню ———
@dp.callback_query()
async def admin_callback_handler(callback_query: CallbackQuery):
    logger.info(f"Callback data: {callback_query.data}")
    data = callback_query.data
    if data == "admin_upload":
        await callback_query.message.answer("📤 Загрузка прогноза...")
        # Начало загрузки фото
        await callback_query.message.answer("Отправьте фото для загрузки.")
        await UploadState.waiting_photo.set()
    elif data == "admin_view":
        await callback_query.message.answer("📊 Просмотр прогнозов...")
    elif data == "admin_clear":
        await callback_query.message.answer("🗑 Прогнозы очищены...")
    elif data == "back_to_start":
        await callback_query.message.answer("🔙 Возвращаемся в начало...")
    await callback_query.answer()

# ——— Обработчик загрузки фото ———
@dp.message(content_types=ContentType.PHOTO, state=UploadState.waiting_photo)
async def handle_photo_upload(message: Message, state: FSMContext):
    # Сохраняем фото в папку, например, /forecasts
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, f"forecasts/{file.file_path.split('/')[-1]}")
    await message.answer("Фото успешно загружено!")
    await state.finish()  # Завершаем состояние

# ——— Обработчик для остальных типов сообщений (обработка текста и проч.) ———
@dp.message()
async def general_handler(message: Message):
    logger.info(f"Обработка сообщения с ID {message.message_id} от пользователя {message.from_user.id}")
    await message.answer("Я получил ваше сообщение! ✅")

# ——— Webhook handlers ———
async def on_start(request):
    return web.Response(text="Bot is running")

async def on_webhook(request):
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error(f"Webhook handling error: {e}")
    return web.Response()

# ——— Установка webhook при старте ———
async def on_app_startup(app):
    info = await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set: {info}")

# ——— Запуск приложения ———
app = web.Application()
app.add_routes([
    web.post(WEBHOOK_PATH, on_webhook),
    web.get("/", on_start),
])
app.on_startup.append(on_app_startup)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
