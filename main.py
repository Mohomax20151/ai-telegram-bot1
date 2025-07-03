import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

# ——— Настройки бота и диспетчера ———
BOT_TOKEN = "8094761598:AAFDmaV_qAKTim2YnkuN8ksQFvwNxds7HLQ"
ADMIN_ID = 6688088575
CATEGORIES = ['football', 'hockey', 'dota', 'cs', 'tennis']

# создаём Bot с глобальным HTML parse_mode
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher(storage=MemoryStorage())

# Webhook URL
WEBHOOK_HOST = "https://ai-telegram-bot1.onrender.com"
WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ——— Определение состояний FSM ———
class UploadState(StatesGroup):
    waiting_photo = State()
    waiting_category = State()

class IntroState(StatesGroup):
    intro_shown = State()

# ——— Вспомогательные функции для клавиатур ———
def generate_categories_keyboard(user_forecasts):
    keyboard = []
    for sport in CATEGORIES:
        count = len(user_forecasts.get(sport, []))
        callback_data = f"buy_{sport}" if count > 0 else "none"
        text = f"{sport.capitalize()} — {count}"
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def admin_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("📤 Загрузить прогноз", callback_data="admin_upload")],
        [InlineKeyboardButton("📊 Просмотр прогнозов", callback_data="admin_view")],
        [InlineKeyboardButton("🗑 Очистить прогнозы", callback_data="admin_clear")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]
    ])

def bottom_keyboard(user_id):
    buttons = [[KeyboardButton("🔮 AI прогнозы")]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("Админ")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ——— Обработчики команд ———
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
            "<b>⚙️ Сейчас:</b>\n"
            "🤖 AI сканирует источники, анализирует коэффициенты, использует нейросети\n"
            "<b>🚀 В будущем:</b> интерактивная аналитика, новые функции"
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

# ——— Webhook Handlers ———
async def on_start(request):
    return web.Response(text="Bot is running")

async def on_webhook(request):
    try:
        json_str = await request.json()
        # передаём bot в контекст валидации
        update = Update.model_validate(json_str, context={"bot": bot})
        # обрабатываем в диспетчере
        await dp.feed_update(update)
    except Exception as e:
        logger.error(f"Ошибка при получении обновления: {e}")
    return web.Response()

async def set_webhook():
    info = await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set: {info}")

# ——— Основная логика запуска сервера и бота ———
app = web.Application()
app.add_routes([
    web.post(WEBHOOK_PATH, on_webhook),
    web.get('/', on_start),
])

async def main():
    logger.info("🤖 Starting bot")
    await set_webhook()
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
