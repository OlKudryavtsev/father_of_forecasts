"""Real implementation extracted from the former bot_runtime monolith."""


from app.runtime import (
    APP_TIMEZONE,
    TOURNAMENT_CODE,
    TOURNAMENT_STARTS_AT_RAW,
    TournamentPrediction,
    User,
    datetime,
    timezone,
)
from app.services.notifications import notify_admins, notify_group_tournament_prediction_saved

def get_tournament_starts_at():
    """Provide bot helper logic for get_tournament_starts_at."""
    dt = datetime.fromisoformat(
        TOURNAMENT_STARTS_AT_RAW.replace("Z", "+00:00")
    )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=APP_TIMEZONE)

    return dt.astimezone(timezone.utc)


def is_tournament_started() -> bool:
    """Provide bot helper logic for is_tournament_started."""
    return datetime.now(timezone.utc) >= get_tournament_starts_at()


def save_tournament_prediction(
        db,
        user: User,
        champion: str,
        runner_up: str,
        third_place: str,
        top_scorer: str,
) -> tuple[bool, str]:
    """Provide bot helper logic for save_tournament_prediction."""
    existing_prediction = db.query(TournamentPrediction).filter(
        TournamentPrediction.user_id == user.id,
        TournamentPrediction.tournament_code == TOURNAMENT_CODE,
    ).first()

    if existing_prediction:
        existing_prediction.champion = champion
        existing_prediction.runner_up = runner_up
        existing_prediction.third_place = third_place
        existing_prediction.top_scorer = top_scorer

        existing_prediction.champion_points = 0
        existing_prediction.runner_up_points = 0
        existing_prediction.third_place_points = 0
        existing_prediction.top_scorer_points = 0
        existing_prediction.points = 0

        db.commit()

        return (
            True,
            "Турнирный прогноз обновлен 🏆\n\n"
            f"1 место: {champion}\n"
            f"2 место: {runner_up}\n"
            f"3 место: {third_place}\n"
            f"Бомбардир: {top_scorer}",
        )

    prediction = TournamentPrediction(
        user_id=user.id,
        tournament_code=TOURNAMENT_CODE,
        champion=champion,
        runner_up=runner_up,
        third_place=third_place,
        top_scorer=top_scorer,
    )

    db.add(prediction)
    db.commit()

    return (
        True,
        "Турнирный прогноз принят 🏆\n\n"
        f"1 место: {champion}\n"
        f"2 место: {runner_up}\n"
        f"3 место: {third_place}\n"
        f"Бомбардир: {top_scorer}",
    )


async def save_tournament_prediction_and_notify_admins(
        db,
        user: User,
        champion: str,
        runner_up: str,
        third_place: str,
        top_scorer: str,
) -> tuple[bool, str]:
    """Handle asynchronous bot workflow for save_tournament_prediction_and_notify_admins."""
    existing_prediction = db.query(TournamentPrediction).filter(
        TournamentPrediction.user_id == user.id,
        TournamentPrediction.tournament_code == TOURNAMENT_CODE,
    ).first()

    was_update = existing_prediction is not None

    success, text = save_tournament_prediction(
        db=db,
        user=user,
        champion=champion,
        runner_up=runner_up,
        third_place=third_place,
        top_scorer=top_scorer,
    )

    if success:
        action_text = "обновил" if was_update else "сделал"

        await notify_admins(
            "🏆 Турнирный прогноз\n\n"
            f"{user.display_name} {action_text} прогноз на турнир\n"
            f"1 место: {champion}\n"
            f"2 место: {runner_up}\n"
            f"3 место: {third_place}\n"
            f"Бомбардир: {top_scorer}",
            exclude_telegram_id=user.telegram_id,
        )

        await notify_group_tournament_prediction_saved(
            user=user,
            is_update=was_update,
        )

    return success, text


def parse_tournament_prediction_payload(text: str):
    """Provide bot helper logic for parse_tournament_prediction_payload."""
    payload = text.replace("/tournament_set", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError("Invalid tournament prediction format")

    champion, runner_up, third_place, top_scorer = parts

    return champion, runner_up, third_place, top_scorer


def parse_tournament_result_payload(text: str):
    """Provide bot helper logic for parse_tournament_result_payload."""
    payload = text.replace("/admin_set_tournament_result", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError("Invalid tournament result format")

    champion, runner_up, third_place, top_scorer = parts

    return champion, runner_up, third_place, top_scorer

