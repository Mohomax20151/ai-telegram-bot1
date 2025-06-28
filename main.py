import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8094761598:AAFDmaV_qAKTim2YnkuN8ksQFvwNxds7HLQ"
ADMIN_ID = 6688088575
CATEGORIES = ['football', 'hockey', 'dota', 'cs', 'tennis']

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class UploadState(StatesGroup):
    waiting_photo = State()
    waiting_category = State()

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message, state: FSMContext):
    await state.update_data(received_forecasts={sport: [] for sport in CATEGORIES})
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 AI прогнозы", callback_data="start_predictions")]
    ])
    await message.answer("Добро пожаловать! Нажмите кнопку ниже для прогноза:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "start_predictions")
async def show_categories(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    received = data.get("received_forecasts", {sport: [] for sport in CATEGORIES})

    # Формируем для каждого спорта список файлов в папке
    categories_data = {}
    for sport in CATEGORIES:
        folder = f"forecasts/{sport}"
        try:
            all_files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        except FileNotFoundError:
            all_files = []
        # Оставляем только те файлы, которые ещё не получил пользователь
        available_files = [f for f in all_files if f not in received.get(sport, [])]
        categories_data[sport] = available_files

    # Сохраним для текущего пользователя, чтобы не перечитывать
    await state.update_data(categories_data=categories_data, received_forecasts=received)

    keyboard = generate_categories_keyboard(categories_data)
    await callback.message.answer("Выбери категорию спорта для получения прогноза:", reply_markup=keyboard)

def generate_categories_keyboard(categories_data):
    keyboard = []
    for sport in CATEGORIES:
        count = len(categories_data.get(sport, []))
        # Если нет доступных прогнозов, кнопка с callback_data = 'none', чтобы игнорировать
        callback_data = f"sport_{sport}" if count > 0 else "none"
        text = f"{sport.capitalize()} — {count}"
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("sport_"))
async def send_forecast(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    sport = callback.data.replace("sport_", "")
    data = await state.get_data()
    categories_data = data.get("categories_data", {})
    received = data.get("received_forecasts", {})

    available_files = categories_data.get(sport, [])
    if not available_files:
        await callback.message.answer(f"Прогнозы по {sport.capitalize()} закончились.")
        return

    next_file = available_files[0]

    # Отправляем файл
    file_path = os.path.join("forecasts", sport, next_file)
    try:
        with open(file_path, 'rb') as photo:
            await bot.send_photo(callback.message.chat.id, photo, caption=f"Прогноз по {sport.capitalize()}")
    except Exception as e:
        await callback.message.answer("Ошибка при отправке файла.")
        return

    # Обновляем списки — добавляем файл в полученные
    received.setdefault(sport, []).append(next_file)
    categories_data[sport].pop(0)

    await state.update_data(categories_data=categories_data, received_forecasts=received)

    # Обновляем клавиатуру с новыми значениями
    keyboard = generate_categories_keyboard(categories_data)
    await callback.message.answer("Выбери категорию спорта для получения прогноза:", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "🔮 AI прогнозы")
async def ai_forecasts_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    received = data.get("received_forecasts", {sport: [] for sport in CATEGORIES})

    categories_data = {}
    for sport in CATEGORIES:
        folder = f"forecasts/{sport}"
        try:
            all_files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        except FileNotFoundError:
            all_files = []
        available_files = [f for f in all_files if f not in received.get(sport, [])]
        categories_data[sport] = available_files

    await state.update_data(categories_data=categories_data)
    keyboard = generate_categories_keyboard(categories_data)

    await message.answer("Выбери категорию спорта для получения прогноза:", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "Админ")
async def bottom_admin(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Загрузить прогноз", callback_data="admin_upload")],
            [InlineKeyboardButton(text="📊 Просмотр прогнозов", callback_data="admin_view")],
            [InlineKeyboardButton(text="🗑 Очистить прогнозы", callback_data="admin_clear")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")]
        ])
        await message.answer("🔧 Админ-панель", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "back_to_start")
async def back_to_start_callback(callback: types.CallbackQuery):
    await callback.answer()
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("🔮 AI прогнозы"))
    await callback.message.answer("Вы вернулись в начало", reply_markup=keyboard)

if __name__ == "__main__":
    print("Бот запущен")
    executor.start_polling(dp, skip_updates=True)
