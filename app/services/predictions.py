"""Real implementation extracted from the former bot_runtime monolith."""


from app.formatters.matches import format_datetime, format_match_label
from app.formatters.predictions import format_advancement_prediction
from app.runtime import Match, Prediction, User, datetime, timezone
from app.services.league_activity import record_user_league_activity

def parse_advancement_choice(choice: str | None):
    """Provide bot helper logic for parse_advancement_choice."""
    if choice is None:
        return False, None

    normalized = choice.lower().strip()

    if normalized in ("none", "no", "нет", "не"):
        return False, None

    if normalized in ("home", "1", "хозяин", "хозяева"):
        return True, "home"

    if normalized in ("away", "2", "гость", "гости"):
        return True, "away"

    raise ValueError("Invalid advancement choice")


def parse_score(score_text: str):
    """Provide bot helper logic for parse_score."""
    normalized = score_text.replace("-", ":").replace(" ", "")

    if ":" not in normalized:
        raise ValueError("Score must contain ':'")

    home_raw, away_raw = normalized.split(":", 1)

    if not home_raw.isdigit() or not away_raw.isdigit():
        raise ValueError("Score must contain numbers")

    return int(home_raw), int(away_raw)


def save_prediction(
        db,
        user: User,
        match: Match,
        pred_home: int,
        pred_away: int,
        advancement_bet_enabled: bool = False,
        predicted_advancing_side: str | None = None,
) -> tuple[bool, str]:
    """Provide bot helper logic for save_prediction."""
    from app.services.matches import is_playoff_match

    now = datetime.now(timezone.utc)

    match_start = match.starts_at
    if match_start.tzinfo is None:
        match_start = match_start.replace(tzinfo=timezone.utc)

    if now >= match_start:
        return (
            False,
            "Ставки на этот матч уже закрыты. "
            "Отец прогнозов суров, но справедлив.",
        )

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
        db.refresh(existing_prediction)

        prediction = existing_prediction
        prefix = "Прогноз обновлен"
    else:
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

        prefix = "Прогноз принят"

    text = (
        f"{prefix}:\n"
        f"{format_match_label(match, include_id=False)}: "
        f"{pred_home}:{pred_away}"
    )

    if is_playoff_match(match):
        text += f"\n{format_advancement_prediction(prediction, match)}"

    try:
        record_user_league_activity(
            db,
            actor=user,
            action_type="match_prediction_updated" if existing_prediction else "match_prediction_created",
            payload={
                "match_id": match.id,
                "match_label": format_match_label(match, include_id=False),
            },
        )
    except Exception:
        # Prediction is already committed; a feed outage must not break it.
        db.rollback()

    return True, text


async def save_prediction_and_notify_admins(
        db,
        user: User,
        match: Match,
        pred_home: int,
        pred_away: int,
        advancement_bet_enabled: bool = False,
        predicted_advancing_side: str | None = None,
) -> tuple[bool, str]:
    """Save match prediction without noisy admin/group notifications."""
    # По просьбе админа отключены уведомления о факте прогноза на матч:
    # - в групповой чат;
    # - администраторам в личку.
    # Само сохранение прогноза и текст ответа пользователю не меняются.
    return save_prediction(
        db=db,
        user=user,
        match=match,
        pred_home=pred_home,
        pred_away=pred_away,
        advancement_bet_enabled=advancement_bet_enabled,
        predicted_advancing_side=predicted_advancing_side,
    )


def user_has_prediction(db, user: User, match: Match) -> bool:
    """Provide bot helper logic for user_has_prediction."""
    prediction = db.query(Prediction).filter(
        Prediction.user_id == user.id,
        Prediction.match_id == match.id,
    ).first()

    return prediction is not None


def build_predictions_text(db, match: Match) -> str:
    """Provide bot helper logic for build_predictions_text."""
    from app.services.matches import is_playoff_match
    now = datetime.now(timezone.utc)

    match_start = match.starts_at
    if match_start.tzinfo is None:
        match_start = match_start.replace(tzinfo=timezone.utc)

    is_revealed = now >= match_start

    users = db.query(User).order_by(User.display_name).all()

    predictions = db.query(Prediction).filter(
        Prediction.match_id == match.id
    ).all()

    predictions_by_user_id = {
        prediction.user_id: prediction
        for prediction in predictions
    }

    start_text = format_datetime(match.starts_at)

    lines = [
        "🔮 Прогнозы на матч",
        format_match_label(match, include_id=True),
        f"Старт: {start_text}",
        "",
    ]

    if is_revealed:
        lines.append("Матч уже начался — прогнозы открыты:")
        lines.append("")

        for user in users:
            prediction = predictions_by_user_id.get(user.id)

            if prediction:
                line = (
                    f"{user.display_name}: "
                    f"{prediction.pred_home}:{prediction.pred_away}"
                )

                if is_playoff_match(match):
                    line += f" ({format_advancement_prediction(prediction, match)})"

                if match.is_finished:
                    line += f" — {prediction.points or 0} очк."

                lines.append(line)
            else:
                lines.append(f"{user.display_name}: прогноза нет")

    else:
        lines.append("До старта матча прогнозы скрыты.")
        lines.append("Видно только, кто уже сделал прогноз:")
        lines.append("")

        for user in users:
            prediction = predictions_by_user_id.get(user.id)

            if prediction:
                lines.append(f"{user.display_name}: ✅ прогноз сделан")
            else:
                lines.append(f"{user.display_name}: ❌ прогноза нет")

    return "\n".join(lines)


def get_user_prediction_match_ids(db, user: User) -> set[int]:
    """Provide bot helper logic for get_user_prediction_match_ids."""
    predictions = db.query(Prediction).filter(
        Prediction.user_id == user.id
    ).all()

    return {
        prediction.match_id
        for prediction in predictions
    }


def get_missing_predictions_for_matches(
        db,
        user: User,
        matches: list[Match],
) -> list[Match]:
    """Provide bot helper logic for get_missing_predictions_for_matches."""
    predicted_match_ids = get_user_prediction_match_ids(db, user)

    return [
        match
        for match in matches
        if match.id not in predicted_match_ids
    ]


def get_prediction_points_breakdown(prediction: Prediction) -> str:
    """Provide bot helper logic for get_prediction_points_breakdown."""
    return (
        f"Очки: {prediction.points or 0} "
        f"({prediction.score_points or 0} за счет/исход, "
        f"{prediction.advancement_points or 0} за проход)"
    )

