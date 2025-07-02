import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, FSInputFile,
    ReplyKeyboardMarkup, KeyboardButton, Message
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup

BOT_TOKEN = "8094761598:AAFDmaV_qAKTim2YnkuN8ksQFvwNxds7HLQ"
ADMIN_ID = 6688088575
CATEGORIES = ['football', 'hockey', 'dota', 'cs', 'tennis']

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

class UploadState(StatesGroup):
    waiting_photo = State()
    waiting_category = State()

class IntroState(StatesGroup):
    intro_shown = State()

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

@dp.callback_query(lambda c: c.data == "start_predictions")
async def handle_intro_button(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await full_start(callback.message, state)

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

@dp.message(lambda m: m.text == "🔮 AI прогнозы")
async def bottom_start(message: Message, state: FSMContext):
    await full_start(message, state)

@dp.message(lambda m: m.text == "Админ")
async def bottom_admin(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔧 Админ-панель", reply_markup=admin_menu_keyboard())

@dp.callback_query(lambda c: c.data == "admin_upload")
async def admin_upload(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.waiting_photo)
    await callback.message.answer("📸 Отправьте прогноз в виде фото")

@dp.message(UploadState.waiting_photo)
async def receive_photo(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("❗ Пожалуйста, отправьте именно фото.")
        return

    file_id = message.photo[-1].file_id
    await state.update_data(photo_id=file_id)
    await state.set_state(UploadState.waiting_category)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[ 
            [InlineKeyboardButton(text=sport.capitalize(), callback_data=f"save_to_{sport}")] 
            for sport in CATEGORIES
        ]
    )
    await message.answer("Выберите категорию для сохранения:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("save_to_"))
async def save_forecast(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo_id = data.get("photo_id")
    sport = callback.data.replace("save_to_", "")

    folder = f"forecasts/{sport}"
    os.makedirs(folder, exist_ok=True)
    files = os.listdir(folder)
    file_name = f"{len(files) + 1}.jpg"

    file = await bot.get_file(photo_id)
    file_path = file.file_path
    await bot.download_file(file_path, os.path.join(folder, file_name))

    await callback.message.answer(f"✅ Прогноз сохранён в категорию {sport.capitalize()}")
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_view")
async def view_forecasts(callback: CallbackQuery):
    report = ""
    for sport in CATEGORIES:
        folder = f"forecasts/{sport}"
        try:
            count = len([f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
        except FileNotFoundError:
            count = 0
        report += f"{sport.capitalize()}: {count} шт.\n"
    await callback.message.answer(f"📊 Статистика прогнозов:\n\n{report}")

@dp.callback_query(lambda c: c.data == "admin_clear")
async def clear_forecasts(callback: CallbackQuery):
    for sport in CATEGORIES:
        folder = f"forecasts/{sport}"
        if os.path.exists(folder):
            for f in os.listdir(folder):
                os.remove(os.path.join(folder, f))
    await callback.message.answer("🗑 Все прогнозы очищены.")

@dp.callback_query(lambda c: c.data == "back_to_start")
async def go_back(callback: CallbackQuery, state: FSMContext):
    await full_start(callback.message, state)

@dp.callback_query()
async def process_payment_choice(callback: CallbackQuery, state: FSMContext):
    if callback.data == "none":
        await callback.answer("Прогнозов в этой категории нет 😞", show_alert=True)
        return

    sport = callback.data.replace("buy_", "")
    data = await state.get_data()
    user_forecasts = data.get("user_forecasts", {})

    files = user_forecasts.get(sport, [])
    if not files:
        await callback.answer("Прогнозы закончились 😞", show_alert=True)
        return

    file_name = files.pop(0)
    file_path = os.path.join(f"forecasts/{sport}", file_name)
    photo = FSInputFile(file_path)

    emoji = "⚽️" if sport == "football" else "🏒" if sport == "hockey" else "🎮"
    await callback.message.answer_photo(photo, caption=f"{sport.capitalize()} {emoji}")

    user_forecasts[sport] = files
    await state.update_data(user_forecasts=user_forecasts)

    try:
        await callback.message.edit_reply_markup(reply_markup=generate_categories_keyboard(user_forecasts))
    except Exception:
        pass

    await callback.answer()

@dp.message(lambda message: message.video)
async def get_video_file_id(message: Message):
    await message.answer(f"<b>file_id:</b> <code>{message.video.file_id}</code>")

async def main():
    print("🤖 Бот запущен.")
    # Получаем порт из переменной окружения PORT
    port = int(os.environ.get('PORT', 10000))  # Порт по умолчанию 10000
    await dp.start_polling(bot)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))  # 10000 — это порт по умолчанию
    executor.start_polling(dp, skip_updates=True)
    asyncio.run(main())
