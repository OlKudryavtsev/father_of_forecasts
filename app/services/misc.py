"""Real implementation extracted from the former bot_runtime monolith."""


from app.constants.teams import TEAM_FLAGS
from app.formatters.matches import format_match_label
from app.runtime import (
    GROUP_CHAT_ID_RAW,
    Message,
    Prediction,
    TOURNAMENT_CODE,
    TournamentPrediction,
    User,
    datetime,
    timezone,
)

def get_group_chat_id() -> int | None:
    """Provide bot helper logic for get_group_chat_id."""
    if not GROUP_CHAT_ID_RAW:
        return None

    try:
        return int(GROUP_CHAT_ID_RAW)
    except ValueError:
        return None


def build_table_rows(db) -> list[dict]:
    """Provide bot helper logic for build_table_rows."""
    users = db.query(User).order_by(User.display_name).all()

    rows = []

    for user in users:
        if getattr(user, "is_bot", False):
            continue

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
                "match_points": match_points,
                "tournament_points": tournament_points,
                "exact_scores": exact_scores,
                "outcomes": outcomes,
                "advancement_plus": advancement_plus,
                "advancement_minus": advancement_minus,
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

    return rows


def get_team_flag(team_name: str | None, api_name: str | None = None) -> str:
    """Provide bot helper logic for get_team_flag."""
    if api_name and api_name in TEAM_FLAGS:
        return TEAM_FLAGS[api_name]

    if team_name and team_name in TEAM_FLAGS:
        return TEAM_FLAGS[team_name]

    return ""


def build_user_summary_context(db, user: User) -> dict:
    """Provide bot helper logic for build_user_summary_context."""
    predictions = db.query(Prediction).filter(
        Prediction.user_id == user.id
    ).all()

    tournament_prediction = db.query(TournamentPrediction).filter(
        TournamentPrediction.user_id == user.id,
        TournamentPrediction.tournament_code == TOURNAMENT_CODE,
    ).first()

    all_users = db.query(User).all()

    leaderboard_rows = []

    for participant in all_users:
        participant_predictions = db.query(Prediction).filter(
            Prediction.user_id == participant.id
        ).all()

        participant_match_points = sum(
            prediction.points or 0
            for prediction in participant_predictions
        )

        participant_tournament_prediction = db.query(TournamentPrediction).filter(
            TournamentPrediction.user_id == participant.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        ).first()

        participant_tournament_points = (
            participant_tournament_prediction.points
            if participant_tournament_prediction
            else 0
        )

        leaderboard_rows.append(
            {
                "user_id": participant.id,
                "name": participant.display_name,
                "points": participant_match_points + participant_tournament_points,
            }
        )

    leaderboard_rows.sort(
        key=lambda row: row["points"],
        reverse=True,
    )

    user_position = None
    leader_points = 0

    if leaderboard_rows:
        leader_points = leaderboard_rows[0]["points"]

    for index, row in enumerate(leaderboard_rows, start=1):
        if row["user_id"] == user.id:
            user_position = index
            break

    total_predictions = len(predictions)

    match_points = sum(prediction.points or 0 for prediction in predictions)

    tournament_points = (
        tournament_prediction.points
        if tournament_prediction
        else 0
    )

    total_points = match_points + tournament_points

    finished_predictions = [
        prediction
        for prediction in predictions
        if prediction.match.is_finished
    ]

    future_predictions = [
        prediction
        for prediction in predictions
        if not prediction.match.is_finished
           and prediction.match.starts_at > datetime.now(timezone.utc)
    ]

    exact_scores = sum(
        1
        for prediction in finished_predictions
        if prediction.score_points == 3
    )

    outcomes = sum(
        1
        for prediction in finished_predictions
        if prediction.score_points == 1
    )

    misses = sum(
        1
        for prediction in finished_predictions
        if (prediction.score_points or 0) == 0
    )

    advancement_plus = sum(
        1
        for prediction in finished_predictions
        if prediction.advancement_points == 1
    )

    advancement_minus = sum(
        1
        for prediction in finished_predictions
        if prediction.advancement_points == -1
    )

    advancement_risk_count = sum(
        1
        for prediction in predictions
        if prediction.advancement_bet_enabled
    )

    best_predictions = sorted(
        finished_predictions,
        key=lambda prediction: (
            prediction.points or 0,
            prediction.score_points or 0,
            prediction.advancement_points or 0,
        ),
        reverse=True,
    )[:3]

    best_predictions_payload = []

    for prediction in best_predictions:
        best_predictions_payload.append(
            {
                "match": format_match_label(prediction.match, include_id=False),
                "prediction": f"{prediction.pred_home}:{prediction.pred_away}",
                "points": prediction.points or 0,
                "score_points": prediction.score_points or 0,
                "advancement_points": prediction.advancement_points or 0,
            }
        )

    missing_nearest = get_missing_predictions_for_matches(
        db=db,
        user=user,
        matches=get_nearest_matchday_matches(db),
    )

    tournament_payload = None

    if tournament_prediction:
        tournament_payload = {
            "champion": tournament_prediction.champion,
            "runner_up": tournament_prediction.runner_up,
            "third_place": tournament_prediction.third_place,
            "top_scorer": tournament_prediction.top_scorer,
            "points": tournament_prediction.points or 0,
        }

    return {
        "user": {
            "name": user.display_name,
            "position": user_position,
            "participants_count": len(all_users),
            "leader_points": leader_points,
            "points_behind_leader": max(leader_points - total_points, 0),
        },
        "points": {
            "total": total_points,
            "match_points": match_points,
            "tournament_points": tournament_points,
        },
        "match_predictions": {
            "total": total_predictions,
            "finished": len(finished_predictions),
            "future": len(future_predictions),
            "exact_scores": exact_scores,
            "outcomes": outcomes,
            "misses": misses,
        },
        "playoff": {
            "risk_count": advancement_risk_count,
            "advancement_plus": advancement_plus,
            "advancement_minus": advancement_minus,
        },
        "tournament_prediction": tournament_payload,
        "best_predictions": best_predictions_payload,
        "missing_predictions_nearest_matchday": len(missing_nearest),
        "available_commands": {
            "missing": "/missing",
            "summary": "/summary",
            "table": "/table",
            "predict": "/predict",
        },
    }


async def send_long_message(message: Message, lines: list[str], chunk_size: int = 3500):
    """Handle asynchronous bot workflow for send_long_message."""
    chunks = []
    current_chunk = ""

    for line in lines:
        line_with_break = line + "\n"

        if len(current_chunk) + len(line_with_break) > chunk_size:
            chunks.append(current_chunk)
            current_chunk = line_with_break
        else:
            current_chunk += line_with_break

    if current_chunk:
        chunks.append(current_chunk)

    for chunk in chunks:
        await message.answer(chunk)

