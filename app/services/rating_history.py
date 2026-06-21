"""Historical leaderboard snapshots for the Mini App rating race."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import os

from sqlalchemy.orm import Session

from app.models import FatherMatchPrediction, League, LeagueMember, Match, Prediction, TournamentPrediction, User
from app.runtime import TOURNAMENT_CODE
from app.scoring import score_match_result_points
from app.services.leagues import league_scoring_start_at


TOURNAMENT_DAY_TIMEZONE = ZoneInfo(os.getenv("TOURNAMENT_DAY_TIMEZONE", "America/New_York"))
FATHER_USER_ID = "father"
FATHER_DISPLAY_NAME = "🤖 Отец прогнозов"
# The matches table keeps the kickoff time but not a dedicated final-whistle
# timestamp. This estimate places snapshots on the timeline at the expected end
# of the match, rather than at the start of play or a later sync timestamp.
MATCH_FINISH_OFFSET = timedelta(hours=2, minutes=10)


def _ensure_utc(value: datetime) -> datetime:
    """Normalise DB values so timezone-aware and legacy values compare safely."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _match_finished_at(match: Match) -> datetime:
    """Return a stable completion moment for plotting historical snapshots."""
    return _ensure_utc(match.starts_at) + MATCH_FINISH_OFFSET


def _snapshot_rows(state: dict[int | str, dict]) -> list[dict]:
    """Rank rows with the same deterministic tiebreakers as the leaderboard."""
    rows = [dict(row) for row in state.values()]
    rows.sort(
        key=lambda row: (
            -int(row.get("points") or 0),
            -int(row.get("exact_scores") or 0),
            -int(row.get("outcomes") or 0),
            str(row.get("name") or "").casefold(),
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def _step_label(value: datetime) -> str:
    """Compact human-friendly label used by the client timeline."""
    local = value.astimezone(TOURNAMENT_DAY_TIMEZONE)
    return local.strftime("%d.%m")


def build_rating_history(db: Session, league: League, current_user_id: int | None = None) -> dict:
    """Build one leaderboard snapshot after each completed match.

    Snapshots are calculated from immutable scored predictions for completed
    matches. No new database table is required: historical rank movement can be
    safely rebuilt on demand and always follows the current scoring rules.
    """
    members = (
        db.query(LeagueMember, User)
        .join(User, User.id == LeagueMember.user_id)
        .filter(
            LeagueMember.league_id == league.id,
            LeagueMember.status == "active",
            User.access_status == "approved",
        )
        .order_by(User.display_name.asc())
        .all()
    )

    users = [user for _membership, user in members if not getattr(user, "is_bot", False)]
    user_ids = [user.id for user in users]
    scoring_start = league_scoring_start_at(league)

    matches_query = db.query(Match).filter(
        Match.tournament_code == TOURNAMENT_CODE,
        Match.is_finished == True,
        Match.score_home.isnot(None),
        Match.score_away.isnot(None),
    )
    if scoring_start is not None:
        matches_query = matches_query.filter(Match.starts_at >= scoring_start)

    # A constant completion offset preserves the kickoff order while allowing
    # the frontend to lay points out according to the estimated final whistle.
    matches = matches_query.order_by(Match.starts_at.asc(), Match.id.asc()).all()
    match_ids = [match.id for match in matches]

    state: dict[int | str, dict] = {
        user.id: {
            "user_id": user.id,
            "name": user.display_name,
            "is_father": False,
            "is_current_user": user.id == current_user_id,
            "points": 0,
            "exact_scores": 0,
            "outcomes": 0,
        }
        for user in users
    }

    # The Father is shown in the normal ranking, so preserve it in the race too.
    state[FATHER_USER_ID] = {
        "user_id": None,
        "race_id": FATHER_USER_ID,
        "name": FATHER_DISPLAY_NAME,
        "is_father": True,
        "is_current_user": False,
        "points": 0,
        "exact_scores": 0,
        "outcomes": 0,
    }

    if not matches:
        return {
            "league_id": league.id,
            "steps": [],
            "participants": [],
            "current_user_id": current_user_id,
            "participant_count": len(state),
        }

    predictions_by_match: dict[int, list[Prediction]] = defaultdict(list)
    if user_ids:
        predictions = (
            db.query(Prediction)
            .filter(Prediction.user_id.in_(user_ids), Prediction.match_id.in_(match_ids))
            .all()
        )
        for prediction in predictions:
            predictions_by_match[prediction.match_id].append(prediction)

    father_predictions = {
        prediction.match_id: prediction
        for prediction in db.query(FatherMatchPrediction)
        .filter(FatherMatchPrediction.match_id.in_(match_ids))
        .all()
    }

    tournament_points_by_user = {
        prediction.user_id: int(prediction.points or 0)
        for prediction in db.query(TournamentPrediction)
        .filter(
            TournamentPrediction.user_id.in_(user_ids),
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        )
        .all()
    } if user_ids else {}

    all_tournament_finished = bool(matches) and (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .filter(Match.is_finished == False)
        .count() == 0
    )

    steps: list[dict] = []
    snapshots_by_id: dict[int | str, list[dict]] = {entry_id: [] for entry_id in state}

    for match_index, match in enumerate(matches):
        for prediction in predictions_by_match.get(match.id, []):
            row = state.get(prediction.user_id)
            if not row:
                continue
            points = int(prediction.points or 0)
            row["points"] += points
            if int(prediction.score_points or 0) == 3:
                row["exact_scores"] += 1
            elif int(prediction.score_points or 0) == 1:
                row["outcomes"] += 1

        father_prediction = father_predictions.get(match.id)
        if father_prediction and match.score_home is not None and match.score_away is not None:
            father_points = score_match_result_points(
                father_prediction.pred_home,
                father_prediction.pred_away,
                match.score_home,
                match.score_away,
            )
            state[FATHER_USER_ID]["points"] += father_points
            if father_points == 3:
                state[FATHER_USER_ID]["exact_scores"] += 1
            elif father_points == 1:
                state[FATHER_USER_ID]["outcomes"] += 1

        # Tournament-prediction points become relevant only after every match of
        # the tournament is complete. During the live tournament this remains 0,
        # exactly as it does in the current leaderboard.
        is_final_snapshot = all_tournament_finished and match_index == len(matches) - 1
        ranking_state = {entry_id: dict(row) for entry_id, row in state.items()}
        if is_final_snapshot:
            for user_id, tournament_points in tournament_points_by_user.items():
                if user_id in ranking_state:
                    ranking_state[user_id]["points"] += tournament_points

        ranked_rows = _snapshot_rows(ranking_state)
        by_id = {
            row.get("race_id", row.get("user_id")): row
            for row in ranked_rows
        }

        finished_at = _match_finished_at(match)
        steps.append(
            {
                "id": f"match-{match.id}",
                "match_id": match.id,
                "date": finished_at.astimezone(TOURNAMENT_DAY_TIMEZONE).date().isoformat(),
                "finished_at": finished_at.isoformat(),
                "starts_at": _ensure_utc(match.starts_at).isoformat(),
                "label": _step_label(finished_at),
                "match_number": match_index + 1,
                "completed_matches": match_index + 1,
                "last_match": f"{match.home_team} — {match.away_team}",
                "last_score": f"{match.score_home}:{match.score_away}",
                "is_current": match_index == len(matches) - 1,
            }
        )

        for entry_id, row in by_id.items():
            snapshots_by_id[entry_id].append(
                {
                    "rank": int(row["rank"]),
                    "points": int(row.get("points") or 0),
                    "exact_scores": int(row.get("exact_scores") or 0),
                    "outcomes": int(row.get("outcomes") or 0),
                }
            )

    participants: list[dict] = []
    for entry_id, row in state.items():
        snapshots = snapshots_by_id.get(entry_id, [])
        if not snapshots:
            continue
        participants.append(
            {
                "user_id": row.get("user_id"),
                "race_id": row.get("race_id", str(row.get("user_id"))),
                "name": row.get("name"),
                "is_father": bool(row.get("is_father")),
                "is_current_user": bool(row.get("is_current_user")),
                "snapshots": snapshots,
            }
        )

    participants.sort(key=lambda row: (row["snapshots"][-1]["rank"], row["name"].casefold()))

    return {
        "league_id": league.id,
        "steps": steps,
        "participants": participants,
        "current_user_id": current_user_id,
        "participant_count": len(participants),
    }
