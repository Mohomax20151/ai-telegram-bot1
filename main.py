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

# Добавление нового состояния для загрузки текста прогнозов
class UploadState(StatesGroup):
    waiting_photo = State()
    waiting_category = State()
    waiting_text = State()  # Новое состояние для загрузки текста

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
        [InlineKeyboardButton(text="📜 Загрузить текстом", callback_data="admin_upload_text")],  # Кнопка для загрузки текстом
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")]
    ])

def bottom_keyboard(user_id):
    buttons = [[KeyboardButton(text="🔮 AI прогнозы")]]
    buttons.append([KeyboardButton(text="📜 Показать прогнозы текстом")])  # Кнопка для получения текста прогнозов
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="Админ")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

@dp.callback_query(lambda c: c.data == "admin_upload")
async def admin_upload(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.waiting_photo)
    await callback.message.answer("📸 Отправьте прогноз в виде фото")

# Новая обработка для загрузки текстовых прогнозов
@dp.callback_query(lambda c: c.data == "admin_upload_text")
async def admin_upload_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.waiting_text)
    await callback.message.answer("📝 Отправьте прогноз в текстовом формате")

@dp.message(UploadState.waiting_text)
async def receive_text(message: Message, state: FSMContext):
    # Сохранение текста в базе данных или другой структуре
    text = message.text
    # Здесь вы можете сохранить текст в БД, например:
    async with SessionLocal() as session:
        text_forecast = TextForecast(text=text)
        session.add(text_forecast)
        await session.commit()

    await message.answer("✅ Прогноз текстом загружен!")
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

# Функция для отправки текстового прогноза
@dp.message(lambda message: message.text == "📜 Показать прогнозы текстом")
async def show_text_forecasts(message: Message):
    # Получаем последний текстовый прогноз из базы данных
    async with SessionLocal() as session:
        result = await session.execute(
            TextForecast.__table__.select()
        )
        forecast = result.scalars().all()

    if forecast:
        for text in forecast:
            await message.answer(f"📜 Прогноз на сегодня:\n{text.text}")
    else:
        await message.answer("❗ Прогнозов текстом нет.")

@dp.callback_query(lambda c: c.data == "admin_clear")
async def clear_forecasts(callback: CallbackQuery):
    # Очищаем и изображения, и текстовые прогнозы
    for sport in CATEGORIES:
        folder = f"forecasts/{sport}"
        if os.path.exists(folder):
            for f in os.listdir(folder):
                os.remove(os.path.join(folder, f))
    
    # Очистка текстовых прогнозов
    async with SessionLocal() as session:
        await session.execute(TextForecast.__table__.delete())
        await session.commit()

    await callback.message.answer("🗑 Все прогнозы (текстовые и изображения) очищены.")

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

    emoji = "⚽️" if sport == "football" else "🏒" if sport == "hockey" else "🎮" if sport == "dota" else "🎮" if sport == "cs" else "🎾"
    await callback.message.answer_photo(photo, caption=f"{sport.capitalize()} {emoji}")

    user_forecasts[sport] = files
    await state.update_data(user_forecasts=user_forecasts)

    try:
        await callback.message.edit_reply_markup(reply_markup=generate_categories_keyboard(user_forecasts))
    except Exception:
        pass

    await callback.answer()

async def main():
    print("🤖 Бот запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
