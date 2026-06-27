"""Real implementation extracted from the former bot_runtime monolith."""


from app.formatters.matches import format_match_label
from app.formatters.misc import format_percent
from app.keyboards.table import build_league_selector_keyboard, build_table_buttons_keyboard
from app.runtime import (
    CallbackQuery,
    Message,
    Match,
    Prediction,
    SessionLocal,
    TOURNAMENT_CODE,
    TournamentPrediction,
    User,
    datetime,
    generate_ai_summary,
    timezone,
)
from app.services.leagues import get_default_or_first_user_league, get_league_by_chat_id, get_user_active_leagues, league_scoring_start_at, require_user_league
from app.services.misc import build_table_rows, build_user_summary_context
from app.services.predictions import get_prediction_points_breakdown
from app.services.users import get_or_create_user

def _format_league_table(db, league) -> str:
    rows = build_table_rows(db, league_id=league.id)
    if not rows:
        return f"🏆 Таблица «{league.name}»\n\nПока нет участников с прогнозами."
    lines = [f"🏆 Таблица «{league.name}»", "№ Игрок — Очки | 🎯 ✅ 🟢 🔴 🏆 📋", ""]
    for index, row in enumerate(rows, start=1):
        name = row.get("name") or "Игрок"
        if len(name) > 16:
            name = name[:15] + "…"
        lines.append(
            f"{index}. {name} — {row.get('points', 0)} | "
            f"{row.get('exact_scores', 0)} {row.get('outcomes', 0)} "
            f"{row.get('advancement_plus', 0)} {row.get('advancement_minus', 0)} "
            f"{row.get('tournament_points', 0)} {row.get('total_predictions', 0)}"
        )
    lines += ["", "🎯 точные счета (+3) · ✅ исходы (+1)", "🟢/🔴 проход (+1/−1) · 🏆 турнир · 📋 матчевые прогнозы"]
    return "\n".join(lines)


def _message_chat_is_group(message: Message) -> bool:
    return getattr(getattr(message, "chat", None), "type", None) in {"group", "supergroup"}


async def table_handler(message: Message):
    """Show a chat-bound table or offer a selector of the user's active leagues."""
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(db, message.from_user)
        if _message_chat_is_group(message):
            league = get_league_by_chat_id(db, message.chat.id)
            if not league:
                await message.answer("Для этого чата не настроена лига. Владелец может указать Chat ID в приложении.")
                return
            await message.answer(_format_league_table(db, league))
            return
        leagues = get_user_active_leagues(db, user)
        if not leagues:
            await message.answer("Ты пока не состоишь ни в одной лиге.")
        elif len(leagues) == 1:
            await message.answer(_format_league_table(db, leagues[0]))
        else:
            await message.answer("🏆 Выбери лигу, таблицу которой хочешь посмотреть:", reply_markup=build_league_selector_keyboard(leagues))
    finally:
        db.close()


async def table_league_callback(callback: CallbackQuery):
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(db, callback.from_user)
        try:
            league_id = int((callback.data or "").split(":", 1)[1])
            league = require_user_league(db, user, league_id)
        except (ValueError, IndexError):
            await callback.answer("Лига недоступна.", show_alert=True)
            return
        if callback.message:
            await callback.message.answer(_format_league_table(db, league))
        await callback.answer()
    finally:
        db.close()


async def summary_handler(message: Message):
    """Handle asynchronous bot workflow for summary_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)
        league = get_league_by_chat_id(db, message.chat.id) if _message_chat_is_group(message) else get_default_or_first_user_league(db, user)
        predictions_query = (
            db.query(Prediction)
            .join(Match, Prediction.match_id == Match.id)
            .filter(Prediction.user_id == user.id, Match.tournament_code == TOURNAMENT_CODE)
        )
        if league and league_scoring_start_at(league) is not None:
            predictions_query = predictions_query.filter(Match.starts_at >= league_scoring_start_at(league))
        predictions = predictions_query.all()

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
            f"📊 Твоя статистика{f' · {league.name}' if league else ''}",
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
        league = get_league_by_chat_id(db, message.chat.id) if _message_chat_is_group(message) else get_default_or_first_user_league(db, user)

        await message.answer(f"🤖 Отец прогнозов изучает твою статистику{f' в лиге «{league.name}»' if league else ''}...")

        context = build_user_summary_context(db, user, league_id=league.id if league else None)

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
    """Backward-compatible alias for /table."""
    await table_handler(message)


async def table_noop_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for table_noop_callback."""
    await callback.answer()

