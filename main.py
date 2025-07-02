import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update, FSInputFile
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

BOT_TOKEN = "8094761598:AAFDmaV_qAKTim2YnkuN8ksQFvwNxds7HLQ"
ADMIN_ID = 6688088575
CATEGORIES = ['football', 'hockey', 'dota', 'cs', 'tennis']

bot = Bot(token=8094761598:AAFDmaV_qAKTim2YnkuN8ksQFvwNxds7HLQ, parse_mode="HTML")  # Убираем ParseMode и используем строку
dp = Dispatcher(storage=MemoryStorage())

# Webhook URL
WEBHOOK_HOST = "https://ai-telegram-bot1.onrender.com"  # Ваш публичный URL на Render
WEBHOOK_PATH = f"/{8094761598:AAFDmaV_qAKTim2YnkuN8ksQFvwNxds7HLQ}/"
WEBHOOK_URL = f"{https://ai-telegram-bot1.onrender.com}{WEBHOOK_PATH}"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния
class UploadState(StatesGroup):
    waiting_photo = State()
    waiting_category = State()

class IntroState(StatesGroup):
    intro_shown = State()

# Функции
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
        [InlineKeyboardButton(text="📤 Загрузить прогноз", callback_data="admin_upload")],
        [InlineKeyboardButton(text="📊 Просмотр прогнозов", callback_data="admin_view")],
        [InlineKeyboardButton(text="🗑 Очистить прогнозы", callback_data="admin_clear")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")]
    ])

def bottom_keyboard(user_id):
    buttons = [[KeyboardButton(text="🔮 AI прогнозы")]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="Админ")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# Обработчики команд
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
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
            "🔐 <b>Количество участников</b> в будущем будет ограничено для стабильности\n"
            "📉 <b>Прибыль сейчас</b> — стабильная, цель: рост процента побед\n\n"
            "<b>⚙️ Что происходит сейчас:</b>\n"
            "🤖 AI:\n"
            "— 📚 Сканирует сотни источников\n"
            "— 📊 Анализирует тренды, коэффициенты\n"
            "— 🧠 Использует нейросети для value-прогнозов\n\n"
            "<b>🚀 Что планируется в будущем:</b>\n"
            "📈 Повышение точности\n"
            "📊 Интерактивная аналитика\n"
            "🧩 Расширение функционала внутри бота"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[ 
            [InlineKeyboardButton(text="🔮 AI прогнозы", callback_data="start_predictions")]
        ])
        await message.answer("Нажмите, чтобы перейти в раздел прогнозов:", reply_markup=keyboard)
        await state.update_data(intro_done=True)
        return

    await full_start(message, state)

# Основная функция обработки запроса Webhook
async def on_start(request):
    return web.Response(text="Bot is running")

# Исправьте обработку в on_webhook:
async def on_webhook(request):
    json_str = await request.json()
    update = Update(**json_str)
    await bot.process_updates([update])  # Новый способ обработки обновлений
    return web.Response()

# Устанавливаем Webhook
async def set_webhook():
    webhook_info = await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set: {webhook_info}")

# Стартуем сервер
app = web.Application()
app.add_routes([web.post(f"/{BOT_TOKEN}/", on_webhook), web.get('/', on_start)])

# Функции бота (не изменяются)
async def full_start(message: Message, state: FSMContext):
    data = await state.get_data()
    user_forecasts = data.get("user_forecasts")

    if not user_forecasts:
        user_forecasts = {}
        for sport in CATEGORIES:
            folder = f"forecasts/{sport}"
            try:
                files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            except FileNotFoundError:
                files = []
            user_forecasts[sport] = files.copy()
        await state.update_data(user_forecasts=user_forecasts)

    await message.answer("Выбери категорию спорта для получения прогноза:", 
                         reply_markup=generate_categories_keyboard(user_forecasts))
    await message.answer("🦅", reply_markup=bottom_keyboard(message.from_user.id))

# Главная функция
async def main():
    logger.info("🤖 Бот запущен.")
    # Устанавливаем webhook перед запуском сервера
    await set_webhook()

    # Запускаем aiohttp сервер на Render
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    # Убираем использование asyncio.run()
    # Платформа уже запускает главный цикл, поэтому избегаем использования asyncio.run
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
