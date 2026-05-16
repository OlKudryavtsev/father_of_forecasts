"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

async def matches_handler(message: Message):
    """Handle asynchronous bot workflow for matches_handler."""
    db = SessionLocal()

    try:
        matches = get_nearest_matchday_matches(db)

        if not matches:
            await message.answer("Нет будущих матчей.")
            return

        text = format_matches_list(
            matches,
            "📅 Ближайший игровой день",
        )

        await message.answer(
            text,
            reply_markup=build_matches_keyboard(matches),
        )

    finally:
        db.close()


async def match_handler(message: Message):
    """Handle asynchronous bot workflow for match_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        parts = message.text.split()

        # Новый кнопочный режим
        if len(parts) == 1:
            matches = get_recent_and_upcoming_matches(db, limit=20)

            if not matches:
                await message.answer("Матчей пока нет.")
                return

            await message.answer(
                "Выбери матч, карточку которого хочешь открыть:",
                reply_markup=build_match_card_keyboard(matches),
            )
            return

        # Старый ручной режим: /match ID
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(
                "Формат команды:\n\n"
                "/match\n\n"
                "или:\n"
                "/match ID\n\n"
                "Например:\n"
                "/match 12"
            )
            return

        match_id = int(parts[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        text = build_match_card_text(db, user, match)

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if not match.is_finished and now < match_start:
            await message.answer(
                text,
                reply_markup=build_matches_keyboard([match]),
            )
        else:
            await message.answer(text)

    finally:
        db.close()


async def matches_all_handler(message: Message):
    """Handle asynchronous bot workflow for matches_all_handler."""
    db = SessionLocal()

    try:
        matches = get_all_available_matches(db, limit=30)

        if not matches:
            await message.answer("Нет будущих матчей.")
            return

        text = format_matches_list(
            matches,
            "📅 Все будущие матчи",
        )

        text += "\n\nПоказаны ближайшие 30 матчей."

        await message.answer(text)

    finally:
        db.close()


async def match_handler(message: Message):
    """Handle asynchronous bot workflow for match_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        parts = message.text.split()

        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(
                "Формат команды:\n\n"
                "/match ID\n\n"
                "Например:\n"
                "/match 12"
            )
            return

        match_id = int(parts[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        predictions_are_revealed = now >= match_start

        my_prediction = db.query(Prediction).filter(
            Prediction.user_id == user.id,
            Prediction.match_id == match.id,
        ).first()

        predictions_count = db.query(Prediction).filter(
            Prediction.match_id == match.id
        ).count()

        users_count = db.query(User).count()

        lines = [
            "⚽ Карточка матча",
            "",
            format_match_label(match, include_id=True),
            f"Старт: {format_datetime(match.starts_at)}",
            f"Статус: {get_match_status(match)}",
            f"Стадия: {match.stage}",
        ]

        if match.group_code:
            lines.append(f"Группа: {match.group_code}")

        if match.match_round:
            if match.stage == "group":
                lines.append(f"Тур: {match.match_round}")
            else:
                lines.append(f"Раунд: {match.match_round}")

        if match.venue or match.city:
            venue_parts = [part for part in [match.venue, match.city] if part]
            lines.append(f"Стадион: {', '.join(venue_parts)}")

        lines.extend(
            [
                "",
                format_match_result(match),
                "",
                f"Прогнозов сделано: {predictions_count} из {users_count}",
                "",
                "Твой прогноз:",
                format_user_match_prediction(
                    my_prediction,
                    match,
                    reveal=True,
                ),
                "",
            ]
        )

        if predictions_are_revealed:
            lines.append("Прогнозы участников:")
            lines.append("")

            users = db.query(User).order_by(User.display_name).all()

            predictions = db.query(Prediction).filter(
                Prediction.match_id == match.id
            ).all()

            predictions_by_user_id = {
                prediction.user_id: prediction
                for prediction in predictions
            }

            for participant in users:
                prediction = predictions_by_user_id.get(participant.id)

                lines.append(
                    f"{participant.display_name}: "
                    f"{format_user_match_prediction(prediction, match, reveal=True)}"
                )
        else:
            lines.append("До старта матча чужие прогнозы скрыты.")
            lines.append("Видно только, кто уже сделал прогноз:")
            lines.append("")

            users = db.query(User).order_by(User.display_name).all()

            predictions = db.query(Prediction).filter(
                Prediction.match_id == match.id
            ).all()

            predictions_by_user_id = {
                prediction.user_id: prediction
                for prediction in predictions
            }

            for participant in users:
                prediction = predictions_by_user_id.get(participant.id)

                lines.append(
                    f"{participant.display_name}: "
                    f"{format_user_match_prediction(prediction, match, reveal=False)}"
                )

        if not match.is_finished and now < match_start:
            await message.answer(
                "\n".join(lines),
                reply_markup=build_matches_keyboard([match]),
            )
        else:
            await message.answer("\n".join(lines))

    finally:
        db.close()


async def match_card_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for match_card_callback."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        match_id = int(callback.data.split(":")[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        text = build_match_card_text(db, user, match)

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if not match.is_finished and now < match_start:
            await callback.message.answer(
                text,
                reply_markup=build_matches_keyboard([match]),
            )
        else:
            await callback.message.answer(text)

        await callback.answer()

    finally:
        db.close()

