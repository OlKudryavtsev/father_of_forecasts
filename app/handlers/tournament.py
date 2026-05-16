"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

async def tournament_set_handler(message: Message, state: FSMContext):
    """Handle asynchronous bot workflow for tournament_set_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if is_tournament_started():
            await message.answer(
                "Прогнозы на итоги турнира уже закрыты. "
                "Турнир стартовал."
            )
            return

        # Если пользователь ввел старый формат через ;
        if ";" in message.text:
            try:
                champion, runner_up, third_place, top_scorer = (
                    parse_tournament_prediction_payload(message.text)
                )
            except ValueError:
                await message.answer(
                    "Формат прогноза на турнир:\n\n"
                    "/tournament_set Чемпион; Финалист; Третье место; Бомбардир\n\n"
                    "Пример:\n"
                    "/tournament_set Аргентина; Франция; Бразилия; Мбаппе"
                )
                return

            _, text = await save_tournament_prediction_and_notify_admins(
                db=db,
                user=user,
                champion=champion,
                runner_up=runner_up,
                third_place=third_place,
                top_scorer=top_scorer,
            )

            await message.answer(text)
            return

        # Новый пошаговый режим
        await state.clear()
        await state.set_state(TournamentPredictionForm.champion)

        await message.answer(
            "Начинаем прогноз на итоги турнира 🏆\n\n"
            "Кто станет чемпионом?\n\n"
            "Напиши название команды, например:\n"
            "Аргентина"
        )

    finally:
        db.close()


async def tournament_handler(message: Message):
    """Handle asynchronous bot workflow for tournament_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        prediction = db.query(TournamentPrediction).filter(
            TournamentPrediction.user_id == user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        ).first()

        if not prediction:
            await message.answer(
                "У тебя пока нет прогноза на итоги турнира.\n\n"
                "Создать прогноз пошагово:\n"
                "/tournament_set\n\n"
                "Или одной строкой:\n"
                "/tournament_set Чемпион; Финалист; Третье место; Бомбардир\n\n"
                "Пример:\n"
                "/tournament_set Аргентина; Франция; Бразилия; Мбаппе"
            )
            return

        await message.answer(
            "🏆 Твой прогноз на итоги турнира:\n\n"
            f"1 место: {prediction.champion}\n"
            f"2 место: {prediction.runner_up}\n"
            f"3 место: {prediction.third_place}\n"
            f"Бомбардир: {prediction.top_scorer}\n\n"
            f"Очки за турнир: {prediction.points}"
        )

    finally:
        db.close()


async def tournament_predictions_handler(message: Message):
    """Handle asynchronous bot workflow for tournament_predictions_handler."""
    db = SessionLocal()

    try:
        users = db.query(User).order_by(User.display_name).all()

        predictions = db.query(TournamentPrediction).filter(
            TournamentPrediction.tournament_code == TOURNAMENT_CODE
        ).all()

        predictions_by_user_id = {
            prediction.user_id: prediction
            for prediction in predictions
        }

        tournament_started = is_tournament_started()

        start_text = format_datetime(get_tournament_starts_at())

        lines = [
            "🏆 Прогнозы на итоги турнира",
            f"Старт турнира: {start_text}",
            "",
        ]

        if tournament_started:
            lines.append("Турнир уже стартовал — прогнозы открыты:")
            lines.append("")

            for user in users:
                prediction = predictions_by_user_id.get(user.id)

                if not prediction:
                    lines.append(f"{user.display_name}: прогноза нет")
                    continue

                lines.append(
                    f"{user.display_name}:\n"
                    f"1 место: {prediction.champion}\n"
                    f"2 место: {prediction.runner_up}\n"
                    f"3 место: {prediction.third_place}\n"
                    f"Бомбардир: {prediction.top_scorer}\n"
                    f"Очки: {prediction.points}"
                )
                lines.append("")

        else:
            lines.append("До старта турнира прогнозы скрыты.")
            lines.append("Видно только, кто уже сделал прогноз:")
            lines.append("")

            for user in users:
                prediction = predictions_by_user_id.get(user.id)

                if prediction:
                    lines.append(f"{user.display_name}: ✅ прогноз сделан")
                else:
                    lines.append(f"{user.display_name}: ❌ прогноза нет")

        await message.answer("\n".join(lines))

    finally:
        db.close()


async def tournament_champion_handler(message: Message, state: FSMContext):
    """Handle asynchronous bot workflow for tournament_champion_handler."""
    champion = message.text.strip()

    if not champion:
        await message.answer("Напиши название команды-чемпиона.")
        return

    await state.update_data(champion=champion)
    await state.set_state(TournamentPredictionForm.runner_up)

    await message.answer(
        f"Чемпион: {champion}\n\n"
        "Кто займет 2 место?"
    )


async def tournament_runner_up_handler(message: Message, state: FSMContext):
    """Handle asynchronous bot workflow for tournament_runner_up_handler."""
    runner_up = message.text.strip()

    if not runner_up:
        await message.answer("Напиши команду, которая займет 2 место.")
        return

    data = await state.get_data()

    if runner_up.lower() == data["champion"].lower():
        await message.answer(
            "Чемпион и финалист не могут быть одной и той же командой.\n"
            "Напиши другую команду."
        )
        return

    await state.update_data(runner_up=runner_up)
    await state.set_state(TournamentPredictionForm.third_place)

    await message.answer(
        f"2 место: {runner_up}\n\n"
        "Кто займет 3 место?"
    )


async def tournament_third_place_handler(message: Message, state: FSMContext):
    """Handle asynchronous bot workflow for tournament_third_place_handler."""
    third_place = message.text.strip()

    if not third_place:
        await message.answer("Напиши команду, которая займет 3 место.")
        return

    data = await state.get_data()

    existing_teams = {
        data["champion"].lower(),
        data["runner_up"].lower(),
    }

    if third_place.lower() in existing_teams:
        await message.answer(
            "Команда на 3 месте не должна совпадать с 1 или 2 местом.\n"
            "Напиши другую команду."
        )
        return

    await state.update_data(third_place=third_place)
    await state.set_state(TournamentPredictionForm.top_scorer)

    await message.answer(
        f"3 место: {third_place}\n\n"
        "Кто станет лучшим бомбардиром турнира?\n\n"
        "Напиши фамилию или имя игрока, например:\n"
        "Мбаппе"
    )


async def tournament_top_scorer_handler(message: Message, state: FSMContext):
    """Handle asynchronous bot workflow for tournament_top_scorer_handler."""
    top_scorer = message.text.strip()

    if not top_scorer:
        await message.answer("Напиши имя или фамилию бомбардира.")
        return

    data = await state.get_data()

    champion = data["champion"]
    runner_up = data["runner_up"]
    third_place = data["third_place"]

    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if is_tournament_started():
            await state.clear()
            await message.answer(
                "Прогнозы на итоги турнира уже закрыты. "
                "Турнир стартовал."
            )
            return

        _, text = await save_tournament_prediction_and_notify_admins(
            db=db,
            user=user,
            champion=champion,
            runner_up=runner_up,
            third_place=third_place,
            top_scorer=top_scorer,
        )

        await state.clear()
        await message.answer(text)

    finally:
        db.close()

