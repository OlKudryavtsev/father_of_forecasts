"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

async def cancel_handler(message: Message, state: FSMContext):
    """Handle asynchronous bot workflow for cancel_handler."""
    current_state = await state.get_state()

    if current_state is None:
        await message.answer("Сейчас нечего отменять.")
        return

    await state.clear()

    await message.answer("Действие отменено.")


async def match_custom_score_handler(message: Message, state: FSMContext):
    """Handle asynchronous bot workflow for match_custom_score_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        data = await state.get_data()
        match_id = data.get("match_id")

        if not match_id:
            await state.clear()
            await message.answer(
                "Не нашел выбранный матч. Начни заново через /predict."
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await state.clear()
            await message.answer(
                "Матч не найден. Начни заново через /predict."
            )
            return

        try:
            pred_home, pred_away = parse_score(message.text)
        except ValueError:
            await message.answer(
                "Не понял счет.\n\n"
                "Введи в формате:\n"
                "3:2\n\n"
                "Или:\n"
                "3-2\n\n"
                "Отмена: /cancel"
            )
            return

        if is_playoff_match(match):
            await state.clear()

            await message.answer(
                f"Счет выбран: {pred_home}:{pred_away}\n\n"
                "Это матч плей-офф. Хочешь рискнуть и поставить, "
                "кто пройдет дальше?\n\n"
                "Если угадаешь — +1 очко.\n"
                "Если не угадаешь — -1 очко.",
                reply_markup=build_advancement_keyboard(
                    match_id=match.id,
                    pred_home=pred_home,
                    pred_away=pred_away,
                    match=match,
                ),
            )
            return

        success, text = await save_prediction_and_notify_admins(
            db=db,
            user=user,
            match=match,
            pred_home=pred_home,
            pred_away=pred_away,
        )

        await state.clear()
        await message.answer(text)

    finally:
        db.close()

