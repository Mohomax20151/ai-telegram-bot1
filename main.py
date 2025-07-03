import os
import logging
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

# ——— Reply "🔮 AI прогнозы" ———
@dp.message(F.text == "🔮 AI прогнозы")
async def bottom_start(message: Message, state: FSMContext):
    await full_start(message, state)

# ——— Показ категорий ———
async def full_start(message: Message, state: FSMContext):
    # Получаем все данные пользователя
    data = await state.get_data()
    # Инициализируем кеш прогнозов только один раз
    if data.get("user_forecasts") is None:
        user_forecasts = {}
        for sport in CATEGORIES:
            folder = f"forecasts/{sport}"
            try:
                files = [
                    f for f in os.listdir(folder)
                    if f.lower().endswith((".png","jpg","jpeg"))
                ]
            except FileNotFoundError:
                files = []
            user_forecasts[sport] = files
        # Сохраняем в state
        await state.update_data(user_forecasts=user_forecasts)
    else:
        user_forecasts = data["user_forecasts"]

    # Отправляем клавиатуру с актуальными числами
    await message.answer(
        "Выбери категорию спорта для получения прогноза:",
        reply_markup=generate_categories_keyboard(user_forecasts)
    )
    await message.answer("🦅", reply_markup=bottom_keyboard(message.from_user.id))

# ——— Админ-панель ———
@dp.message(F.text == "Админ")
async def admin_menu_handler(message: Message):
    logger.info(f"Запрошено админ-меню пользователем {message.from_user.id}")
    await message.answer("Выберите действие:", reply_markup=admin_menu_keyboard())

# ——— Админ callback’ы ———
@dp.callback_query(F.data == "admin_upload")
async def admin_upload(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📤 Загрузка прогнозов…\nОтправьте фото для загрузки.")
    await state.set_state(UploadState.waiting_photo)

@dp.callback_query(F.data == "admin_view")
async def admin_view(callback: CallbackQuery):
    report = ""
    for sport in CATEGORIES:
        folder = f"forecasts/{sport}"
        try:
            count = len([f for f in os.listdir(folder) if f.lower().endswith((".png","jpg","jpeg"))])
        except FileNotFoundError:
            count = 0
        report += f"{sport.capitalize()}: {count} шт.\n"
    await callback.answer()
    await callback.message.answer(f"📊 Статистика прогнозов:\n\n{report}")

@dp.callback_query(F.data == "admin_clear")
async def admin_clear(callback: CallbackQuery):
    global TEXT_FORECAST
    TEXT_FORECAST = ""  # Очищаем текстовый прогноз
    for sport in CATEGORIES:
        folder = f"forecasts/{sport}"
        if os.path.exists(folder):
            for f in os.listdir(folder):
                os.remove(os.path.join(folder, f))
    await callback.answer()
    await callback.message.answer("🗑 Все прогнозы очищены.")

@dp.callback_query(F.data == "admin_upload_text")
async def admin_upload_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Отправьте текст прогнозов:")
    await state.set_state(UploadState.waiting_text)

# ——— Загрузка текста ———
@dp.message(StateFilter(UploadState.waiting_text))
async def handle_text_upload(message: Message, state: FSMContext):
    global TEXT_FORECAST
    TEXT_FORECAST = message.text
    await message.answer("Текстовый прогноз сохранён!")
    await state.clear()

# ——— Загрузка фото ———
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
    await callback.answer()
    await callback.message.answer(f"✅ Прогноз сохранён в категорию {sport.capitalize()}")
    await state.clear()

# ——— Покупка прогноза ———
@dp.callback_query(F.data.startswith("buy_"))
async def buy_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_forecasts = data.get("user_forecasts", {})
    sport = callback.data.replace("buy_", "")
    files = user_forecasts.get(sport, [])
    if not files:
        await callback.answer("Прогнозов в этой категории нет 😞", show_alert=True)
        return

    # Отправляем фотографию прогноза
    file_name = files.pop(0)
    path = os.path.join(f"forecasts/{sport}", file_name)
    photo = FSInputFile(path)
    emojis = {"football":"⚽️","hockey":"🏒","dota":"🎮","cs":"🔫","tennis":"🎾"}
    caption = f"{sport.capitalize()} {emojis.get(sport,'')}"
    await callback.message.answer_photo(photo, caption=caption)

    # Обновляем state
    user_forecasts[sport] = files
    await state.update_data(user_forecasts=user_forecasts)

    # Сразу редактируем кнопки с актуальным числом прогнозов
    await callback.message.edit_reply_markup(
        reply_markup=generate_categories_keyboard(user_forecasts)
    )

    await callback.answer()

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
