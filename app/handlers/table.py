"""Real implementation extracted from the former bot_runtime monolith."""


from app.formatters.matches import format_match_label
from app.formatters.misc import format_percent
from app.keyboards.table import build_table_buttons_keyboard
from app.runtime import (
    CallbackQuery,
    Message,
    Prediction,
    SessionLocal,
    TOURNAMENT_CODE,
    TournamentPrediction,
    User,
    datetime,
    generate_ai_summary,
    timezone,
)
from app.services.misc import build_table_rows, build_user_summary_context
from app.services.predictions import get_prediction_points_breakdown
from app.services.users import get_or_create_user

async def table_handler(message: Message):
    """Handle asynchronous bot workflow for table_handler."""
    db = SessionLocal()

    try:
        users = db.query(User).all()

        rows = []

        for user in users:
            predictions = db.query(Prediction).filter(
                Prediction.user_id == user.id
            ).all()

            tournament_prediction = db.query(TournamentPrediction).filter(
                TournamentPrediction.user_id == user.id,
                TournamentPrediction.tournament_code == TOURNAMENT_CODE,
            ).first()

            match_points = sum(
                prediction.points or 0
                for prediction in predictions
            )

            tournament_points = (
                tournament_prediction.points
                if tournament_prediction
                else 0
            )

            total_points = match_points + tournament_points

            exact_scores = sum(
                1
                for prediction in predictions
                if prediction.score_points == 3
            )

            outcomes = sum(
                1
                for prediction in predictions
                if prediction.score_points == 1
            )

            advancement_plus = sum(
                1
                for prediction in predictions
                if prediction.advancement_points == 1
            )

            advancement_minus = sum(
                1
                for prediction in predictions
                if prediction.advancement_points == -1
            )

            total_predictions = len(predictions)

            rows.append(
                {
                    "name": user.display_name,
                    "points": total_points,
                    "exact_scores": exact_scores,
                    "outcomes": outcomes,
                    "advancement_plus": advancement_plus,
                    "advancement_minus": advancement_minus,
                    "tournament_points": tournament_points,
                    "total_predictions": total_predictions,
                }
            )

        rows.sort(
            key=lambda row: (
                row["points"],
                row["exact_scores"],
                row["outcomes"],
            ),
            reverse=True,
        )

        if not rows:
            await message.answer("Таблица пока пустая.")
            return

        lines = [
            "🏆 Таблица «Отец прогнозов»",
            "№ Игрок — Очки | 🎯 ✅ 🟢 🔴 🏆 📋",
            "",
        ]

        for index, row in enumerate(rows, start=1):
            name = row["name"]

            # Чтобы длинные имена не ломали таблицу
            if len(name) > 16:
                name = name[:15] + "…"

            lines.append(
                f"{index}. {name} — {row['points']} | "
                f"{row['exact_scores']} "
                f"{row['outcomes']} "
                f"{row['advancement_plus']} "
                f"{row['advancement_minus']} "
                f"{row['tournament_points']} "
                f"{row['total_predictions']}"
            )

        lines.append("")
        lines.append("🎯 точные счета (+3)")
        lines.append("✅ угаданные исходы (+1)")
        lines.append("🟢 угаданные проходы (+1)")
        lines.append("🔴 неугаданные проходы (-1)")
        lines.append("🏆 очки за прогноз на турнир")
        lines.append("📋 всего матчевых прогнозов")

        await message.answer("\n".join(lines))

    finally:
        db.close()


async def summary_handler(message: Message):
    """Handle asynchronous bot workflow for summary_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        predictions = db.query(Prediction).filter(
            Prediction.user_id == user.id
        ).all()

        tournament_prediction = db.query(TournamentPrediction).filter(
            TournamentPrediction.user_id == user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        ).first()

        total_predictions = len(predictions)

        match_points = sum(prediction.points or 0 for prediction in predictions)
        tournament_points = (
            tournament_prediction.points
            if tournament_prediction
            else 0
        )

        total_points = match_points + tournament_points

        exact_scores = sum(
            1
            for prediction in predictions
            if prediction.score_points == 3
        )

        outcomes = sum(
            1
            for prediction in predictions
            if prediction.score_points == 1
        )

        misses = sum(
            1
            for prediction in predictions
            if prediction.match.is_finished
            and (prediction.score_points or 0) == 0
        )

        finished_predictions = sum(
            1
            for prediction in predictions
            if prediction.match.is_finished
        )

        advancement_plus = sum(
            1
            for prediction in predictions
            if prediction.advancement_points == 1
        )

        advancement_minus = sum(
            1
            for prediction in predictions
            if prediction.advancement_points == -1
        )

        advancement_risk_count = sum(
            1
            for prediction in predictions
            if prediction.advancement_bet_enabled
        )

        upcoming_predictions = sum(
            1
            for prediction in predictions
            if not prediction.match.is_finished
            and prediction.match.starts_at > datetime.now(timezone.utc)
        )

        best_predictions = sorted(
            [
                prediction
                for prediction in predictions
                if prediction.match.is_finished
            ],
            key=lambda prediction: (
                prediction.points or 0,
                prediction.score_points or 0,
                prediction.advancement_points or 0,
            ),
            reverse=True,
        )

        lines = [
            "📊 Твоя статистика",
            "",
            f"Участник: {user.display_name}",
            f"Всего очков: {total_points}",
            f"Очки за матчи: {match_points}",
            f"Очки за турнир: {tournament_points}",
            "",
            "Матчевые прогнозы:",
            f"Всего прогнозов: {total_predictions}",
            f"Завершенных прогнозов: {finished_predictions}",
            f"Будущих прогнозов: {upcoming_predictions}",
            "",
            f"🎯 Точные счета: {exact_scores} "
            f"({format_percent(exact_scores, finished_predictions)})",
            f"✅ Исходы: {outcomes} "
            f"({format_percent(outcomes, finished_predictions)})",
            f"❌ Без очков за счет/исход: {misses} "
            f"({format_percent(misses, finished_predictions)})",
            "",
            "Плей-офф:",
            f"Рисковых ставок на проход: {advancement_risk_count}",
            f"🟢 Угадано проходов: {advancement_plus}",
            f"🔴 Не угадано проходов: {advancement_minus}",
            "",
        ]

        if tournament_prediction:
            lines.extend(
                [
                    "Турнирный прогноз:",
                    f"1 место: {tournament_prediction.champion}",
                    f"2 место: {tournament_prediction.runner_up}",
                    f"3 место: {tournament_prediction.third_place}",
                    f"Бомбардир: {tournament_prediction.top_scorer}",
                    f"Очки: {tournament_prediction.points}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "Турнирный прогноз:",
                    "пока не сделан",
                    "",
                    "Создать: /tournament_set",
                    "",
                ]
            )

        if best_predictions:
            lines.append("Лучшие прогнозы:")

            for prediction in best_predictions[:3]:
                match = prediction.match

                lines.append(
                    f"{format_match_label(match, include_id=True)}\n"
                    f"Прогноз: {prediction.pred_home}:{prediction.pred_away}\n"
                    f"{get_prediction_points_breakdown(prediction)}"
                )
                lines.append("")
        else:
            lines.append("Завершенных матчей с твоими прогнозами пока нет.")

        await message.answer("\n".join(lines))

    finally:
        db.close()


async def ai_summary_handler(message: Message):
    """Handle asynchronous bot workflow for ai_summary_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        await message.answer("🤖 Отец прогнозов изучает твою статистику...")

        context = build_user_summary_context(db, user)

        try:
            text = generate_ai_summary(context)
        except Exception as error:
            print(f"AI summary error: {error}")

            await message.answer(
                "ИИ-сводка сейчас не получилась. "
                "Обычная статистика доступна через /summary."
            )
            return

        await message.answer(text)

    finally:
        db.close()


async def table_buttons_handler(message: Message):
    """Handle asynchronous bot workflow for table_buttons_handler."""
    db = SessionLocal()

    try:
        rows = build_table_rows(db)

        if not rows:
            await message.answer("Таблица пока пустая.")
            return

        await message.answer(
            "🏆 Турнирная таблица\n\n"
            "О — очки всего\n"
            "🎯 — точные счета\n"
            "✅ — угаданные исходы\n"
            "🏆 — очки за прогноз на турнир",
            reply_markup=build_table_buttons_keyboard(rows),
        )

    finally:
        db.close()


async def table_noop_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for table_noop_callback."""
    await callback.answer()

