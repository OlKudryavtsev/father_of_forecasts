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
from app.services.league_activity import record_user_league_activity


def get_tournament_starts_at(tournament_code: str | None = None):
    """Provide bot helper logic for get_tournament_starts_at."""
    dt = datetime.fromisoformat(
        TOURNAMENT_STARTS_AT_RAW.replace("Z", "+00:00")
    )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=APP_TIMEZONE)

    return dt.astimezone(timezone.utc)


def is_tournament_started(tournament_code: str | None = None, db=None) -> bool:
    """Provide bot helper logic for is_tournament_started."""
    if db is not None and tournament_code is not None:
        try:
            from app.services.tournaments import tournament_started_for_code
            return tournament_started_for_code(db, tournament_code)
        except Exception:
            pass
    return datetime.now(timezone.utc) >= get_tournament_starts_at(tournament_code)


def _to_utc(dt):
    """Return timezone-aware UTC datetime."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _tournament_has_third_place(db, tournament_code: str | None = None) -> bool:
    selected_tournament_code = tournament_code or TOURNAMENT_CODE
    try:
        from app.services.tournaments import get_tournament
        tournament = get_tournament(db, selected_tournament_code)
        return bool(getattr(tournament, "has_third_place_match", True))
    except Exception:
        return True


def _tournament_prediction_payload(
    champion: str,
    runner_up: str,
    third_place: str,
    top_scorer: str,
    has_third_place: bool,
) -> dict:
    payload = {"champion": champion, "runner_up": runner_up, "top_scorer": top_scorer}
    if has_third_place:
        payload["third_place"] = third_place
    return payload


def _tournament_prediction_message(
    prefix: str,
    champion: str,
    runner_up: str,
    third_place: str,
    top_scorer: str,
    has_third_place: bool,
) -> str:
    lines = [
        prefix,
        "",
        f"Победитель: {champion}",
        f"Финалист: {runner_up}",
    ]
    if has_third_place:
        lines.append(f"3 место: {third_place}")
    lines.append(f"Бомбардир: {top_scorer}")
    return "\n".join(lines)


def tournament_prediction_submit_state(db, user: User, tournament_code: str | None = None) -> dict:
    """Return whether the user may create/update a tournament prediction.

    Before tournament start all users can create/update their tournament prediction.
    After tournament start, only users registered after the start and without an
    existing prediction may create it once. This keeps old locked predictions
    immutable while allowing late approved participants to join during the World Cup.
    """
    selected_tournament_code = tournament_code or TOURNAMENT_CODE
    existing_prediction = db.query(TournamentPrediction).filter(
        TournamentPrediction.user_id == user.id,
        TournamentPrediction.tournament_code == selected_tournament_code,
    ).first()

    tournament_started = is_tournament_started(selected_tournament_code, db=db)
    if not tournament_started:
        return {
            "can_submit": True,
            "is_closed": False,
            "is_late_entry": False,
            "existing_prediction": existing_prediction,
        }

    registered_at = _to_utc(getattr(user, "access_requested_at", None) or getattr(user, "created_at", None))
    starts_at = get_tournament_starts_at(selected_tournament_code)
    is_late_entry = bool(registered_at and registered_at >= starts_at)
    can_submit = existing_prediction is None and is_late_entry

    return {
        "can_submit": can_submit,
        "is_closed": not can_submit,
        "is_late_entry": is_late_entry,
        "existing_prediction": existing_prediction,
    }


def save_tournament_prediction(
        db,
        user: User,
        champion: str,
        runner_up: str,
        third_place: str,
        top_scorer: str,
        tournament_code: str | None = None,
) -> tuple[bool, str]:
    """Provide bot helper logic for save_tournament_prediction."""
    selected_tournament_code = tournament_code or TOURNAMENT_CODE
    has_third_place = _tournament_has_third_place(db, selected_tournament_code)
    if not has_third_place:
        third_place = ""
    existing_prediction = db.query(TournamentPrediction).filter(
        TournamentPrediction.user_id == user.id,
        TournamentPrediction.tournament_code == selected_tournament_code,
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
        try:
            record_user_league_activity(
                db,
                actor=user,
                action_type="tournament_prediction_updated",
                payload=_tournament_prediction_payload(champion, runner_up, third_place, top_scorer, has_third_place),
            )
        except Exception:
            db.rollback()

        return (
            True,
            _tournament_prediction_message(
                "Турнирный прогноз обновлен 🏆",
                champion,
                runner_up,
                third_place,
                top_scorer,
                has_third_place,
            ),
        )

    prediction = TournamentPrediction(
        user_id=user.id,
        tournament_code=selected_tournament_code,
        champion=champion,
        runner_up=runner_up,
        third_place=third_place,
        top_scorer=top_scorer,
    )

    db.add(prediction)
    db.commit()
    try:
        record_user_league_activity(
            db,
            actor=user,
            action_type="tournament_prediction_created",
            payload=_tournament_prediction_payload(champion, runner_up, third_place, top_scorer, has_third_place),
        )
    except Exception:
        db.rollback()

    return (
        True,
        _tournament_prediction_message(
            "Турнирный прогноз принят 🏆",
            champion,
            runner_up,
            third_place,
            top_scorer,
            has_third_place,
        ),
    )


async def save_tournament_prediction_and_notify_admins(
        db,
        user: User,
        champion: str,
        runner_up: str,
        third_place: str,
        top_scorer: str,
        tournament_code: str | None = None,
) -> tuple[bool, str]:
    """Handle asynchronous bot workflow for save_tournament_prediction_and_notify_admins."""
    selected_tournament_code = tournament_code or TOURNAMENT_CODE
    has_third_place = _tournament_has_third_place(db, selected_tournament_code)
    if not has_third_place:
        third_place = ""
    existing_prediction = db.query(TournamentPrediction).filter(
        TournamentPrediction.user_id == user.id,
        TournamentPrediction.tournament_code == selected_tournament_code,
    ).first()

    was_update = existing_prediction is not None

    success, text = save_tournament_prediction(
        db=db,
        user=user,
        champion=champion,
        runner_up=runner_up,
        third_place=third_place,
        top_scorer=top_scorer,
        tournament_code=selected_tournament_code,
    )

    if success:
        action_text = "обновил" if was_update else "сделал"

        await notify_admins(
            _tournament_prediction_message(
                f"🏆 Турнирный прогноз\n\n{user.display_name} {action_text} прогноз на турнир",
                champion,
                runner_up,
                third_place,
                top_scorer,
                has_third_place,
            ),
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

