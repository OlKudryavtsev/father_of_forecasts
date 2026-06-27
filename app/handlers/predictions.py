"""Real implementation extracted from the former bot_runtime monolith."""


from app.formatters.matches import format_datetime, format_match_label, format_missing_matches_list
from app.formatters.predictions import format_advancement_prediction
from app.keyboards.matches import build_matches_keyboard
from app.keyboards.predictions import build_advancement_keyboard, build_predictions_matches_keyboard, build_score_keyboard
from app.runtime import (
    CallbackQuery,
    FSMContext,
    Match,
    Message,
    Prediction,
    SessionLocal,
    datetime,
    timezone,
)
from app.services.matches import get_all_available_matches, get_nearest_matchday_matches, get_recent_and_upcoming_matches, is_playoff_match
from app.services.predictions import build_predictions_text, get_missing_predictions_for_matches, parse_advancement_choice, parse_score, save_prediction_and_notify_admins
from app.services.leagues import get_default_or_first_user_league, get_league_by_chat_id
from app.services.users import get_or_create_user
from app.states import MatchPredictionForm

async def predict_handler(message: Message):
    """Handle asynchronous bot workflow for predict_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        parts = message.text.split()

        if len(parts) == 1:
            matches = get_nearest_matchday_matches(db)

            if not matches:
                await message.answer("Нет доступных матчей для прогноза.")
                return

            await message.answer(
                "Выбери матч ближайшего игрового дня:",
                reply_markup=build_matches_keyboard(matches),
            )
            return

        if len(parts) not in (3, 4):
            await message.answer(
                "Формат прогноза:\n"
                "/predict ID СЧЕТ\n\n"
                "Например:\n"
                "/predict 1 2:1\n\n"
                "Для плей-офф:\n"
                "/predict ID СЧЕТ home\n"
                "/predict ID СЧЕТ away\n"
                "/predict ID СЧЕТ none"
            )
            return

        _, match_id_raw, score_raw, *advancement_raw = parts

        if not match_id_raw.isdigit():
            await message.answer("ID матча должен быть числом.")
            return

        match_id = int(match_id_raw)

        try:
            pred_home, pred_away = parse_score(score_raw)
        except ValueError:
            await message.answer(
                "Не понял счет. Используй формат 2:1 или 2-1."
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if now >= match_start:
            await message.answer(
                "Ставки на этот матч уже закрыты. "
                "Отец прогнозов суров, но справедлив."
            )
            return

        advancement_bet_enabled = False
        predicted_advancing_side = None

        if is_playoff_match(match):
            choice = advancement_raw[0] if advancement_raw else "none"

            try:
                advancement_bet_enabled, predicted_advancing_side = (
                    parse_advancement_choice(choice)
                )
            except ValueError:
                await message.answer(
                    "Не понял ставку на проход.\n\n"
                    "Используй:\n"
                    "home — пройдет первая команда\n"
                    "away — пройдет вторая команда\n"
                    "none — не ставить на проход\n\n"
                    "Пример:\n"
                    "/predict 5 1:1 home"
                )
                return
        else:
            if advancement_raw:
                await message.answer(
                    "Это не матч плей-офф. "
                    "Ставка на проход доступна только в матчах на вылет."
                )
                return
        success, text = await save_prediction_and_notify_admins(
            db=db,
            user=user,
            match=match,
            pred_home=pred_home,
            pred_away=pred_away,
            advancement_bet_enabled=advancement_bet_enabled,
            predicted_advancing_side=predicted_advancing_side,
        )

        await message.answer(text)
        """
        existing_prediction = db.query(Prediction).filter(
            Prediction.user_id == user.id,
            Prediction.match_id == match.id,
        ).first()

        if existing_prediction:
            existing_prediction.pred_home = pred_home
            existing_prediction.pred_away = pred_away
            existing_prediction.advancement_bet_enabled = advancement_bet_enabled
            existing_prediction.predicted_advancing_side = predicted_advancing_side
            db.commit()

            text = (
                f"Прогноз обновлен:\n"
                f"{match.home_team} — {match.away_team}: "
                f"{pred_home}:{pred_away}"
            )

            if is_playoff_match(match):
                text += f"\n{format_advancement_prediction(existing_prediction, match)}"

            await message.answer(text)
            return

        prediction = Prediction(
            user_id=user.id,
            match_id=match.id,
            pred_home=pred_home,
            pred_away=pred_away,
            advancement_bet_enabled=advancement_bet_enabled,
            predicted_advancing_side=predicted_advancing_side,
        )

        db.add(prediction)
        db.commit()
        db.refresh(prediction)

        text = (
            f"Прогноз принят:\n"
            f"{match.home_team} — {match.away_team}: "
            f"{pred_home}:{pred_away}"
        )

        if is_playoff_match(match):
            text += f"\n{format_advancement_prediction(prediction, match)}"

        await message.answer(text) 
        """

    finally:
        db.close()


async def mybets_handler(message: Message):
    """Handle asynchronous bot workflow for mybets_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        predictions = db.query(Prediction).filter(
            Prediction.user_id == user.id
        ).all()

        if not predictions:
            await message.answer("У тебя пока нет прогнозов.")
            return

        lines = ["🎯 Мои прогнозы:\n"]

        for prediction in predictions:
            match = prediction.match

            line = (
                f"{format_match_label(match, include_id=False)}: "
                f"{prediction.pred_home}:{prediction.pred_away}"
            )

            if is_playoff_match(match):
                line += f" ({format_advancement_prediction(prediction, match)})"

            lines.append(line)

        await message.answer("\n".join(lines))

    finally:
        db.close()


async def predictions_handler(message: Message):
    """Handle asynchronous bot workflow for predictions_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)
        league = get_league_by_chat_id(db, message.chat.id) if message.chat.type in {"group", "supergroup"} else get_default_or_first_user_league(db, user)
        league_id = league.id if league else None
        parts = message.text.split()

        # Новый кнопочный режим
        if len(parts) == 1:
            matches = get_recent_and_upcoming_matches(db, limit=20)

            if not matches:
                await message.answer("Матчей пока нет.")
                return

            await message.answer(
                "Выбери матч, по которому хочешь посмотреть прогнозы:",
                reply_markup=build_predictions_matches_keyboard(matches, league_id=league_id),
            )
            return

        # Старый ручной режим: /predictions ID
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(
                "Формат команды:\n\n"
                "/predictions\n\n"
                "или:\n"
                "/predictions ID\n\n"
                "Например:\n"
                "/predictions 12"
            )
            return

        match_id = int(parts[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        await message.answer(build_predictions_text(db, match, league_id=league_id))

    finally:
        db.close()


async def predict_match_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for predict_match_callback."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        parts = (callback.data or "").split(":")
        match_id = int(parts[1])
        league_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if now >= match_start:
            await callback.message.answer(
                "Ставки на этот матч уже закрыты."
            )
            await callback.answer()
            return

        await callback.message.answer(
            f"Выбран матч:\n"
            f"{format_match_label(match, include_id=False)}\n"
            f"Старт: {format_datetime(match.starts_at)}\n\n"
            f"Выбери счет:",
            reply_markup=build_score_keyboard(match.id),
        )

        await callback.answer()

    finally:
        db.close()


async def predict_score_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for predict_score_callback."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        _, match_id_raw, pred_home_raw, pred_away_raw = callback.data.split(":")

        match_id = int(match_id_raw)
        pred_home = int(pred_home_raw)
        pred_away = int(pred_away_raw)

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        if is_playoff_match(match):
            await callback.message.answer(
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

            await callback.answer()
            return

        success, text = await save_prediction_and_notify_admins(
            db=db,
            user=user,
            match=match,
            pred_home=pred_home,
            pred_away=pred_away,
        )

        await callback.message.answer(text)
        await callback.answer()

    finally:
        db.close()


async def predict_advancement_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for predict_advancement_callback."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        _, match_id_raw, pred_home_raw, pred_away_raw, choice = (
            callback.data.split(":")
        )

        match_id = int(match_id_raw)
        pred_home = int(pred_home_raw)
        pred_away = int(pred_away_raw)

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        try:
            advancement_bet_enabled, predicted_advancing_side = (
                parse_advancement_choice(choice)
            )
        except ValueError:
            await callback.message.answer("Не понял ставку на проход.")
            await callback.answer()
            return

        success, text = await save_prediction_and_notify_admins(
            db=db,
            user=user,
            match=match,
            pred_home=pred_home,
            pred_away=pred_away,
            advancement_bet_enabled=advancement_bet_enabled,
            predicted_advancing_side=predicted_advancing_side,
        )

        await callback.message.answer(text)
        await callback.answer()

    finally:
        db.close()


async def predict_custom_callback(callback: CallbackQuery, state: FSMContext):
    """Handle asynchronous bot workflow for predict_custom_callback."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        match_id = int(callback.data.split(":")[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if now >= match_start:
            await callback.message.answer(
                "Ставки на этот матч уже закрыты."
            )
            await callback.answer()
            return

        await state.clear()
        await state.set_state(MatchPredictionForm.custom_score)
        await state.update_data(match_id=match.id)

        await callback.message.answer(
            f"Введи счет для матча:\n"
            f"{format_match_label(match, include_id=False)}\n\n"
            "Например:\n"
            "3:2\n\n"
            "Можно также через дефис:\n"
            "3-2\n\n"
            "Отмена: /cancel"
        )

        await callback.answer()

    finally:
        db.close()


async def predict_all_handler(message: Message):
    """Handle asynchronous bot workflow for predict_all_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        matches = get_all_available_matches(db)

        if not matches:
            await message.answer("Нет доступных матчей для прогноза.")
            return

        await message.answer(
            "Выбери матч для прогноза:",
            reply_markup=build_matches_keyboard(matches),
        )

    finally:
        db.close()


async def missing_handler(message: Message):
    """Handle asynchronous bot workflow for missing_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        matches = get_nearest_matchday_matches(db)

        if not matches:
            await message.answer("Нет будущих матчей.")
            return

        missing_matches = get_missing_predictions_for_matches(
            db=db,
            user=user,
            matches=matches,
        )

        text = format_missing_matches_list(
            missing_matches,
            "❌ Матчи ближайшего игрового дня без твоего прогноза",
        )

        if missing_matches:
            await message.answer(
                text,
                reply_markup=build_matches_keyboard(missing_matches),
            )
        else:
            await message.answer(text)

    finally:
        db.close()


async def missing_all_handler(message: Message):
    """Handle asynchronous bot workflow for missing_all_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        matches = get_all_available_matches(db, limit=30)

        if not matches:
            await message.answer("Нет будущих матчей.")
            return

        missing_matches = get_missing_predictions_for_matches(
            db=db,
            user=user,
            matches=matches,
        )

        text = format_missing_matches_list(
            missing_matches,
            "❌ Ближайшие матчи без твоего прогноза",
        )

        text += "\n\nПроверены ближайшие 30 будущих матчей."

        if missing_matches:
            await message.answer(
                text,
                reply_markup=build_matches_keyboard(missing_matches),
            )
        else:
            await message.answer(text)

    finally:
        db.close()


async def predictions_match_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for predictions_match_callback."""
    db = SessionLocal()

    try:
        parts = (callback.data or "").split(":")
        match_id = int(parts[1])
        league_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        await callback.message.answer(build_predictions_text(db, match, league_id=league_id))
        await callback.answer()

    finally:
        db.close()

