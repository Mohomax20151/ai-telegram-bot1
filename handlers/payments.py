from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, LabeledPrice, FSInputFile, ContentType

router = Router()

SPORTS = {
    "dota": 3,
    "football": 2,
    "tennis": 4,
    "csgo": 1,
    "hockey": 3
}

PRICE_PER_FORECAST = 100  # в звёздах

@router.callback_query(F.data.startswith("buy_"))
async def send_invoice(callback: CallbackQuery):
    category = callback.data.replace("buy_", "")
    max_count = SPORTS.get(category, 1)

    buttons = [
        [InlineKeyboardButton(text=f"{i} прогноз", callback_data=f"pay_{category}_{i}")]
        for i in range(1, max_count + 1)
    ]
    await callback.message.edit_text(f"Выберите количество прогнозов {category.capitalize()}:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("pay_"))
async def process_payment_choice(callback: CallbackQuery):
    _, category, count_str = callback.data.split("_")
    count = int(count_str)

    title = f"Прогнозы AI: {category.capitalize()} x{count}"
    description = f"Вы получите {count} прогноз(ов) по дисциплине {category.capitalize()}."
    payload = f"{category}_forecasts_{count}"
    currency = "USD"
    total_price = PRICE_PER_FORECAST * count
    prices = [LabeledPrice(label=title, amount=total_price * 100)]

    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=title,
        description=description,
        payload=payload,
        provider_token="STARS",
        currency=currency,
        prices=prices,
        start_parameter="ai_forecasts"
    )
    await callback.answer()

@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def handle_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split("_forecasts_")
    category = parts[0]
    count = int(parts[1]) if len(parts) > 1 else 1

    import os
    folder_path = f"data/forecasts/{category}/"
    files = sorted(os.listdir(folder_path))
    for file_name in files[:count]:
        path = os.path.join(folder_path, file_name)
        await message.answer_photo(photo=FSInputFile(path))

    await message.answer("Спасибо за покупку! Удачного анализа!")
