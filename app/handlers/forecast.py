"""Real implementation extracted from the former bot_runtime monolith."""


from app.keyboards.matches import build_forecast_matches_keyboard
from app.runtime import CallbackQuery, Match, Message, SessionLocal
from app.services.forecast import build_forecast_text
from app.services.matches import get_nearest_matchday_matches

async def forecast_handler(message: Message):
    """Handle asynchronous bot workflow for forecast_handler."""
    db = SessionLocal()

    try:
        parts = message.text.split()

        if len(parts) == 1:
            matches = get_nearest_matchday_matches(
                db,
                matchdays_count=3,
            )

            if not matches:
                await message.answer("Нет будущих матчей для прогноза.")
                return

            await message.answer(
                "🤖 Прогноз Отца прогнозов\nВыбери матч для ИИ-прогноза.\nПоказаны ближайшие 3 игровых дня:",
                reply_markup=build_forecast_matches_keyboard(matches),
            )
            return

        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(
                "Формат:\n\n"
                "/forecast\n\n"
                "или:\n"
                "/forecast ID\n\n"
                "Например:\n"
                "/forecast 12"
            )
            return

        match_id = int(parts[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        await message.answer(build_forecast_text(db, match))

    finally:
        db.close()


async def forecast_match_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for forecast_match_callback."""
    db = SessionLocal()

    try:
        match_id = int(callback.data.split(":")[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        await callback.message.answer(build_forecast_text(db, match))
        await callback.answer()

    finally:
        db.close()

