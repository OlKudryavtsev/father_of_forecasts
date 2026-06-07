"""FastAPI endpoints used by the Telegram Mini App."""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import random

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, get_db
from app.models import (
    FantasyPlayer,
    FantasyTeam,
    FantasyTeamPlayer,
    HistoricalArchiveCard,
    Match,
    Prediction,
    QuizAnswer,
    QuizQuestion,
    TournamentPrediction,
    User,
    WorldCupFact,
)
from app.runtime import TOURNAMENT_CODE
from app.services.matches import get_all_available_matches, get_nearest_matchday_matches, is_playoff_match
from app.services.misc import build_table_rows, get_team_flag
from app.services.predictions import save_prediction_and_notify_admins
from app.services.tournament import get_tournament_starts_at, is_tournament_started, save_tournament_prediction_and_notify_admins
from app.services.forecast import build_forecast_text
from app.services.tournament_forecast import get_top_scorer_candidates, get_top_scorer_hint, serialize_father_tournament_forecast
from app.team_names import get_team_name_ru

router = APIRouter(prefix="/api/webapp", tags=["Telegram Mini App"])


class PredictionPayload(BaseModel):
    """Payload for creating/updating a match prediction."""

    match_id: int
    pred_home: int = Field(ge=0, le=20)
    pred_away: int = Field(ge=0, le=20)
    advancement_bet_enabled: bool = False
    predicted_advancing_side: str | None = None


class TournamentPredictionPayload(BaseModel):
    """Payload for saving the user's tournament prediction."""

    champion: str
    runner_up: str
    third_place: str
    top_scorer: str


class QuizAnswerPayload(BaseModel):
    """Payload for saving an answer in the Mini App quick quiz."""

    question_id: int
    selected_option: str


class FantasyTeamPayload(BaseModel):
    """Payload for saving a user's fantasy squad."""

    formation: str = "4-3-3"
    player_ids: list[int] = Field(min_length=15, max_length=15)
    starting_player_ids: list[int] = Field(min_length=11, max_length=11)
    captain_player_id: int


def _ensure_utc(dt: datetime) -> datetime:
    """Return timezone-aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def _serialize_match(match: Match, user_prediction: Prediction | None = None) -> dict:
    """Serialize a match for the Mini App API."""
    home_name = get_team_name_ru(match.home_team)
    away_name = get_team_name_ru(match.away_team)

    return {
        "id": match.id,
        "label": _match_label(match),
        "home_team": home_name,
        "away_team": away_name,
        "home_flag": get_team_flag(home_name, getattr(match, "home_team_api_name", None)),
        "away_flag": get_team_flag(away_name, getattr(match, "away_team_api_name", None)),
        "stage": match.stage,
        "match_round": match.match_round,
        "group_code": match.group_code,
        "starts_at": _ensure_utc(match.starts_at).isoformat(),
        "venue": match.venue,
        "city": match.city,
        "score_home": match.score_home,
        "score_away": match.score_away,
        "winner_side": match.winner_side,
        "is_finished": bool(match.is_finished),
        "is_playoff": is_playoff_match(match),
        "prediction": _serialize_prediction(user_prediction) if user_prediction else None,
    }


def _match_label(match: Match) -> str:
    """Build a compact human-readable match label."""
    home_name = get_team_name_ru(match.home_team)
    away_name = get_team_name_ru(match.away_team)
    home_flag = get_team_flag(home_name, getattr(match, "home_team_api_name", None))
    away_flag = get_team_flag(away_name, getattr(match, "away_team_api_name", None))

    parts = []

    if match.match_round:
        parts.append(f"Тур {match.match_round}" if match.stage == "group" else match.match_round)

    if match.group_code:
        parts.append(f"Группа {match.group_code}")

    postfix = f". {'. '.join(parts)}" if parts else ""
    return f"{home_name} {home_flag} — {away_flag} {away_name}{postfix}".strip()


def _serialize_prediction(prediction: Prediction) -> dict:
    """Serialize a user's prediction."""
    return {
        "id": prediction.id,
        "pred_home": prediction.pred_home,
        "pred_away": prediction.pred_away,
        "advancement_bet_enabled": bool(prediction.advancement_bet_enabled),
        "predicted_advancing_side": prediction.predicted_advancing_side,
        "score_points": prediction.score_points or 0,
        "advancement_points": prediction.advancement_points or 0,
        "points": prediction.points or 0,
    }


def _prediction_by_match_id(db: Session, user: User, matches: list[Match]) -> dict[int, Prediction]:
    """Return user's predictions mapped by match id."""
    match_ids = [match.id for match in matches]

    if not match_ids:
        return {}

    predictions = (
        db.query(Prediction)
        .filter(Prediction.user_id == user.id, Prediction.match_id.in_(match_ids))
        .all()
    )

    return {prediction.match_id: prediction for prediction in predictions}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    """Return current Mini App user profile."""
    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "is_admin": bool(current_user.is_admin),
    }


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return compact dashboard data for the Mini App home page."""
    nearest_matches = get_nearest_matchday_matches(db, matchdays_count=1)
    predictions_by_match = _prediction_by_match_id(db, current_user, nearest_matches)

    all_available_matches = get_all_available_matches(db, limit=100)
    all_predictions_by_match = _prediction_by_match_id(db, current_user, all_available_matches)

    missing_matches = [
        match
        for match in all_available_matches
        if match.id not in all_predictions_by_match
    ]

    nearest_missing_matches = [
        match
        for match in nearest_matches
        if match.id not in predictions_by_match
    ]

    tournament_prediction = (
        db.query(TournamentPrediction)
        .filter(
            TournamentPrediction.user_id == current_user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    tournament_starts_at = get_tournament_starts_at()
    days_until_tournament = max((tournament_starts_at.date() - datetime.now(timezone.utc).date()).days, 0)

    table_rows = build_table_rows(db)
    current_rank = None
    current_points = 0

    for index, row in enumerate(table_rows, start=1):
        if row["name"] == current_user.display_name:
            current_rank = index
            current_points = row["points"]
            break

    return {
        "user": {
            "id": current_user.id,
            "display_name": current_user.display_name,
        },
        "rank": current_rank,
        "points": current_points,
        "nearest_matches": [
            _serialize_match(match, predictions_by_match.get(match.id))
            for match in nearest_matches
        ],
        "nearest_missing_predictions_count": len(nearest_missing_matches),
        "nearest_missing_matches_preview": [
            _serialize_match(match, predictions_by_match.get(match.id))
            for match in nearest_missing_matches[:5]
        ],
        "missing_predictions_count": len(missing_matches),
        "missing_matches_preview": [
            _serialize_match(match)
            for match in missing_matches[:5]
        ],
        "tournament": {
            "days_until_start": days_until_tournament,
            "has_prediction": tournament_prediction is not None,
            "is_started": is_tournament_started(),
            "starts_at": tournament_starts_at.isoformat(),
        },
    }


@router.get("/matches")
def get_matches(
    scope: str = Query(default="all", regex="^(nearest|all|missing)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return matches for predictions or browsing."""
    if scope == "nearest":
        matches = get_nearest_matchday_matches(db, matchdays_count=1)
    else:
        matches = get_all_available_matches(db, limit=100)

    predictions_by_match = _prediction_by_match_id(db, current_user, matches)

    if scope == "missing":
        matches = [match for match in matches if match.id not in predictions_by_match]

    return {
        "matches": [
            _serialize_match(match, predictions_by_match.get(match.id))
            for match in matches
        ]
    }


@router.get("/matches/{match_id}")
def get_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a single match card with current user's prediction."""
    match = db.query(Match).filter(Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    prediction = (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id, Prediction.match_id == match.id)
        .first()
    )

    return {"match": _serialize_match(match, prediction)}




@router.get("/matches/{match_id}/predictions")
def get_match_predictions_visibility(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return participants who predicted a match; reveal scores only after kickoff."""
    match = db.query(Match).filter(Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    has_started = _ensure_utc(match.starts_at) <= datetime.now(timezone.utc)
    predictions = (
        db.query(Prediction, User)
        .join(User, User.id == Prediction.user_id)
        .filter(Prediction.match_id == match.id)
        .order_by(User.display_name.asc())
        .all()
    )

    participants = []

    for prediction, user in predictions:
        item = {
            "user_id": user.id,
            "display_name": user.display_name,
            "username": user.username,
            "has_prediction": True,
        }

        if has_started:
            item.update(
                {
                    "pred_home": prediction.pred_home,
                    "pred_away": prediction.pred_away,
                    "advancement_bet_enabled": bool(prediction.advancement_bet_enabled),
                    "predicted_advancing_side": prediction.predicted_advancing_side,
                    "score_points": prediction.score_points or 0,
                    "advancement_points": prediction.advancement_points or 0,
                    "points": prediction.points or 0,
                }
            )

        participants.append(item)

    return {
        "match": _serialize_match(match),
        "has_started": has_started,
        "participants_count": len(participants),
        "participants": participants,
    }


@router.get("/forecast/{match_id}")
async def get_forecast_for_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return AI forecast text for a selected match."""
    match = db.query(Match).filter(Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    try:
        text = await asyncio.to_thread(build_forecast_text, db, match)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Forecast generation failed: {error}") from error

    return {"match_id": match.id, "text": text}


@router.get("/tournament-teams")
def get_tournament_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return unique tournament teams for Mini App autocomplete fields."""
    matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.asc())
        .all()
    )

    teams_by_name: dict[str, dict] = {}

    for match in matches:
        for display_name, api_name in [
            (match.home_team, getattr(match, "home_team_api_name", None)),
            (match.away_team, getattr(match, "away_team_api_name", None)),
        ]:
            if not display_name or display_name == "TBD":
                continue

            name = get_team_name_ru(display_name)

            if name not in teams_by_name:
                teams_by_name[name] = {
                    "name": name,
                    "api_name": api_name or display_name,
                    "flag": get_team_flag(name, api_name or display_name),
                }

    teams = sorted(teams_by_name.values(), key=lambda item: item["name"])

    return {"teams": teams}


@router.post("/predictions")
async def save_prediction_endpoint(
    payload: PredictionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create or update current user's prediction for a match."""
    match = db.query(Match).filter(Match.id == payload.match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if payload.predicted_advancing_side not in (None, "home", "away"):
        raise HTTPException(status_code=400, detail="Invalid advancing side")

    if not is_playoff_match(match) and payload.advancement_bet_enabled:
        raise HTTPException(status_code=400, detail="Advancement bet is only available for playoff matches")

    success, text = await save_prediction_and_notify_admins(
        db=db,
        user=current_user,
        match=match,
        pred_home=payload.pred_home,
        pred_away=payload.pred_away,
        advancement_bet_enabled=payload.advancement_bet_enabled,
        predicted_advancing_side=payload.predicted_advancing_side,
    )

    if not success:
        raise HTTPException(status_code=400, detail=text)

    prediction = (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id, Prediction.match_id == match.id)
        .first()
    )

    return {
        "ok": True,
        "message": text,
        "match": _serialize_match(match, prediction),
    }


@router.get("/table")
def get_table(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return tournament leaderboard with compact participant progress details."""
    rows = build_table_rows(db)

    users_by_name = {
        user.display_name: user
        for user in db.query(User).all()
    }

    available_matches_count = len(get_all_available_matches(db, limit=1000))

    for index, row in enumerate(rows, start=1):
        user = users_by_name.get(row["name"])
        tournament_prediction = None
        fantasy_team = None
        user_predictions_count = row.get("total_predictions", 0)

        if user:
            tournament_prediction = (
                db.query(TournamentPrediction)
                .filter(
                    TournamentPrediction.user_id == user.id,
                    TournamentPrediction.tournament_code == TOURNAMENT_CODE,
                )
                .first()
            )
            user_predictions_count = (
                db.query(Prediction)
                .filter(Prediction.user_id == user.id)
                .count()
            )
            fantasy_team = (
                db.query(FantasyTeam)
                .filter(
                    FantasyTeam.user_id == user.id,
                    FantasyTeam.tournament_code == TOURNAMENT_CODE,
                )
                .first()
            )

        exact_scores = row.get("exact_scores", 0)
        outcomes = row.get("outcomes", 0)
        advancement_plus = row.get("advancement_plus", 0)
        advancement_minus = row.get("advancement_minus", 0)
        match_points = row.get("match_points", 0)
        tournament_points = row.get("tournament_points", 0)
        total_points = row.get("points", 0)
        accuracy_base = max(1, user_predictions_count)
        successful_predictions = exact_scores + outcomes

        row["rank"] = index
        row["is_current_user"] = row["name"] == current_user.display_name
        row["match_predictions_count"] = user_predictions_count
        row["match_predictions_available"] = available_matches_count
        row["match_predictions_progress"] = (
            f"{user_predictions_count}/{available_matches_count}"
            if available_matches_count
            else str(user_predictions_count)
        )
        row["tournament_prediction_count"] = 4 if tournament_prediction else 0
        row["tournament_prediction_total"] = 4
        row["tournament_prediction_progress"] = "4/4" if tournament_prediction else "0/4"
        row["has_tournament_prediction"] = tournament_prediction is not None
        fantasy_selected_count = len(fantasy_team.players) if fantasy_team else 0
        row["fantasy_team_progress"] = f"{fantasy_selected_count}/15"
        row["fantasy_team_complete"] = fantasy_selected_count == 15 and bool(fantasy_team and fantasy_team.captain_player_id)
        row["fantasy_points"] = fantasy_team.points if fantasy_team else 0
        row["points_with_fantasy"] = row["points"] + row["fantasy_points"]
        row["exact_scores"] = exact_scores
        row["outcomes"] = outcomes
        row["advancement_plus"] = advancement_plus
        row["advancement_minus"] = advancement_minus
        row["match_points"] = match_points
        row["tournament_points"] = tournament_points
        row["points"] = total_points
        row["successful_predictions"] = successful_predictions
        row["accuracy_percent"] = round(successful_predictions * 100 / accuracy_base)

    return {"rows": rows}


@router.get("/tournament-forecast")
def get_father_tournament_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return static Father Forecast for tournament outcomes."""
    return {"forecast": serialize_father_tournament_forecast()}


@router.get("/top-scorer-candidates")
def get_top_scorer_candidates_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return top scorer candidates and hint for Mini App."""
    return {
        "candidates": get_top_scorer_candidates(),
        "hint": get_top_scorer_hint(),
    }


@router.get("/tournament-prediction/me")
def get_my_tournament_prediction(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current user's long-term tournament prediction."""
    prediction = (
        db.query(TournamentPrediction)
        .filter(
            TournamentPrediction.user_id == current_user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    return {
        "prediction": _serialize_tournament_prediction(prediction) if prediction else None,
        "is_closed": is_tournament_started(),
    }


@router.post("/tournament-prediction")
async def save_tournament_prediction_endpoint(
    payload: TournamentPredictionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create or update current user's tournament prediction."""
    if is_tournament_started():
        raise HTTPException(status_code=400, detail="Tournament predictions are closed")

    success, text = await save_tournament_prediction_and_notify_admins(
        db=db,
        user=current_user,
        champion=payload.champion.strip(),
        runner_up=payload.runner_up.strip(),
        third_place=payload.third_place.strip(),
        top_scorer=payload.top_scorer.strip(),
    )

    if not success:
        raise HTTPException(status_code=400, detail=text)

    prediction = (
        db.query(TournamentPrediction)
        .filter(
            TournamentPrediction.user_id == current_user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    return {"ok": True, "message": text, "prediction": _serialize_tournament_prediction(prediction)}


@router.get("/tournament-predictions")
def get_tournament_predictions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return all tournament predictions with pre-start privacy rules."""
    users = db.query(User).order_by(User.display_name).all()
    predictions = (
        db.query(TournamentPrediction)
        .filter(TournamentPrediction.tournament_code == TOURNAMENT_CODE)
        .all()
    )
    predictions_by_user = {prediction.user_id: prediction for prediction in predictions}
    revealed = is_tournament_started()

    rows = []

    for user in users:
        prediction = predictions_by_user.get(user.id)
        rows.append(
            {
                "user_name": user.display_name,
                "has_prediction": prediction is not None,
                "prediction": _serialize_tournament_prediction(prediction) if revealed and prediction else None,
            }
        )

    return {"revealed": revealed, "rows": rows}


def _serialize_tournament_prediction(prediction: TournamentPrediction | None) -> dict | None:
    """Serialize a tournament prediction."""
    if not prediction:
        return None

    return {
        "champion": prediction.champion,
        "runner_up": prediction.runner_up,
        "third_place": prediction.third_place,
        "top_scorer": prediction.top_scorer,
        "champion_points": prediction.champion_points or 0,
        "runner_up_points": prediction.runner_up_points or 0,
        "third_place_points": prediction.third_place_points or 0,
        "top_scorer_points": prediction.top_scorer_points or 0,
        "points": prediction.points or 0,
    }




def _favorite_score(predictions: list[Prediction]) -> str | None:
    """Return the user's most frequent predicted score."""
    if not predictions:
        return None

    counts: dict[str, int] = {}

    for prediction in predictions:
        key = f"{prediction.pred_home}:{prediction.pred_away}"
        counts[key] = counts.get(key, 0) + 1

    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _profile_status(points: int, exact_scores: int, total_predictions: int, missing_count: int) -> str:
    """Return a playful profile status based on current user stats."""
    if missing_count > 0:
        return "Думающий стратег"
    if total_predictions == 0:
        return "Тень будущего прогноза"
    if exact_scores >= 5:
        return "Снайпер счета"
    if points >= 25:
        return "Кандидат в Отцы"
    if total_predictions >= 20:
        return "Стабильный участник"
    return "Футбольный шаман в разогреве"


def _profile_badges(
    *,
    exact_scores: int,
    outcomes: int,
    total_predictions: int,
    missing_count: int,
    tournament_prediction: TournamentPrediction | None,
    rank: int | None,
) -> list[dict]:
    """Build achievement badges for the Mini App profile."""
    badges = [
        {
            "code": "early_bird",
            "title": "Хладнокровный",
            "description": "Все доступные прогнозы сделаны",
            "icon": "check",
            "earned": total_predictions > 0 and missing_count == 0,
            "progress": 1 if total_predictions > 0 and missing_count == 0 else 0,
            "goal": 1,
        },
        {
            "code": "sniper",
            "title": "Снайпер",
            "description": "Точные счета",
            "icon": "target",
            "earned": exact_scores >= 3,
            "progress": min(exact_scores, 3),
            "goal": 3,
        },
        {
            "code": "oracle",
            "title": "Оракул исходов",
            "description": "Угаданные исходы",
            "icon": "fire",
            "earned": outcomes >= 5,
            "progress": min(outcomes, 5),
            "goal": 5,
        },
        {
            "code": "marathon",
            "title": "Марафонец",
            "description": "Прогнозы на матчи",
            "icon": "ball",
            "earned": total_predictions >= 20,
            "progress": min(total_predictions, 20),
            "goal": 20,
        },
        {
            "code": "longterm",
            "title": "Долгосрочник",
            "description": "Турнирный прогноз заполнен",
            "icon": "cup",
            "earned": tournament_prediction is not None,
            "progress": 1 if tournament_prediction else 0,
            "goal": 1,
        },
        {
            "code": "top3",
            "title": "На пьедестале",
            "description": "Попасть в топ-3 рейтинга",
            "icon": "rank",
            "earned": bool(rank and rank <= 3),
            "progress": 1 if rank and rank <= 3 else 0,
            "goal": 1,
        },
    ]

    return badges



FANTASY_FORMATION = "4-3-3"
FANTASY_SQUAD_POSITION_LIMITS = {
    "Goalkeeper": 2,
    "Defender": 5,
    "Midfielder": 5,
    "Attacker": 3,
}
FANTASY_STARTER_POSITION_LIMITS = {
    "Goalkeeper": 1,
    "Defender": 4,
    "Midfielder": 3,
    "Attacker": 3,
}
FANTASY_POSITION_LABELS = {
    "Goalkeeper": "ВР",
    "Defender": "ЗЩ",
    "Midfielder": "ПЗ",
    "Attacker": "НП",
}
FANTASY_CATEGORY_LIMITS_GROUP = {1: 3, 2: 3, 3: 3, 4: 2}
FANTASY_CATEGORY_LIMITS_R16 = {1: 4, 2: 4, 3: 4, 4: 3}
FANTASY_MAX_FROM_ONE_TEAM_BY_STAGE = {
    "group_1": 3,
    "group_2": 3,
    "group_3": 3,
    "r16": 4,
    "quarter": 5,
    "semi": 6,
    "final": 8,
}
FANTASY_FREE_TRANSFERS = {
    "group_1": None,
    "group_2": 2,
    "group_3": 2,
    "r16": None,
    "quarter": 4,
    "semi": 5,
    "final": 6,
}
FANTASY_EXTRA_TRANSFER_PENALTY = 3


def _parse_round_number(value: str | None) -> int | None:
    """Parse group round number from match_round/api text."""
    if not value:
        return None

    text = str(value).lower()
    for number in (1, 2, 3):
        if str(number) in text:
            return number
    return None


def _fantasy_stage_key(match: Match) -> str:
    """Return fantasy transfer window key for a match."""
    if match.stage == "group":
        return f"group_{_parse_round_number(match.match_round) or 1}"

    text = f"{match.stage or ''} {match.match_round or ''} {match.api_league_round or ''}".lower()

    if "round of 16" in text or "1/8" in text or "16" in text:
        return "r16"
    if "quarter" in text or "1/4" in text:
        return "quarter"
    if "semi" in text or "1/2" in text:
        return "semi"
    if "third" in text or "3" in text:
        return "final"
    if "final" in text:
        return "final"

    return match.stage or "future"


def _fantasy_stage_title(key: str) -> str:
    """Return user-facing fantasy stage title."""
    return {
        "group_1": "1-й тур группового этапа",
        "group_2": "2-й тур группового этапа",
        "group_3": "3-й тур группового этапа",
        "r16": "1/8 финала",
        "quarter": "1/4 финала",
        "semi": "1/2 финала",
        "final": "финал и матч за 3 место",
    }.get(key, key)


def _fantasy_round_state(db: Session) -> dict:
    """Return current fantasy transfer window and next deadline."""
    now = datetime.now(timezone.utc)
    matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.asc())
        .all()
    )

    windows: dict[str, datetime] = {}
    order = ["group_1", "group_2", "group_3", "r16", "quarter", "semi", "final"]

    for match in matches:
        key = _fantasy_stage_key(match)
        starts_at = _ensure_utc(match.starts_at)
        if key not in windows or starts_at < windows[key]:
            windows[key] = starts_at

    upcoming_key = None
    upcoming_deadline = None

    for key in order:
        deadline = windows.get(key)
        if deadline and deadline > now:
            upcoming_key = key
            upcoming_deadline = deadline
            break

    if not upcoming_key:
        return {
            "key": "locked",
            "title": "Трансферы закрыты",
            "deadline_at": None,
            "is_locked": True,
            "free_transfers": 0,
            "extra_transfer_penalty": FANTASY_EXTRA_TRANSFER_PENALTY,
            "max_from_one_team": 8,
            "category_limits": {},
            "category_limits_enabled": False,
        }

    if upcoming_key == "group_1":
        category_limits = FANTASY_CATEGORY_LIMITS_GROUP
    elif upcoming_key == "r16":
        category_limits = FANTASY_CATEGORY_LIMITS_R16
    elif upcoming_key.startswith("group_"):
        category_limits = FANTASY_CATEGORY_LIMITS_GROUP
    else:
        category_limits = {}

    return {
        "key": upcoming_key,
        "title": _fantasy_stage_title(upcoming_key),
        "deadline_at": upcoming_deadline.isoformat(),
        "is_locked": False,
        "free_transfers": FANTASY_FREE_TRANSFERS.get(upcoming_key),
        "extra_transfer_penalty": FANTASY_EXTRA_TRANSFER_PENALTY,
        "max_from_one_team": FANTASY_MAX_FROM_ONE_TEAM_BY_STAGE.get(upcoming_key, 3),
        "category_limits": category_limits,
        "category_limits_enabled": bool(category_limits),
    }


def _load_baseline_ids(value: str | None) -> set[int]:
    """Load baseline player IDs from serialized text."""
    if not value:
        return set()
    try:
        return {int(item) for item in json.loads(value)}
    except Exception:
        return set()


def _fantasy_category_title(category: int) -> str:
    """Return readable FIFA ranking category title."""
    return {
        1: "Элита",
        2: "Сильные претенденты",
        3: "Середина",
        4: "Аутсайдеры и дебютанты",
    }.get(category, "Категория")


def _serialize_fantasy_player(player: FantasyPlayer) -> dict:
    """Serialize a fantasy player for Mini App."""
    return {
        "id": player.id,
        "external_player_id": player.external_player_id,
        "external_team_id": player.external_team_id,
        "name": player.player_name,
        "team_name": player.team_name,
        "team_display_name": player.team_display_name,
        "team_flag": player.team_flag or get_team_flag(player.team_display_name, player.team_name),
        "age": player.age,
        "number": player.number,
        "position": player.position,
        "position_label": FANTASY_POSITION_LABELS.get(player.position, player.position),
        "photo": player.photo,
        "fifa_rank": player.fifa_rank,
        "fifa_category": player.fifa_category,
        "fifa_category_title": _fantasy_category_title(player.fifa_category),
        "is_active": bool(player.is_active),
    }


def _serialize_fantasy_team(team: FantasyTeam | None) -> dict | None:
    """Serialize user's fantasy team."""
    if not team:
        return None

    team_players = sorted(
        team.players,
        key=lambda item: (
            {"Goalkeeper": 0, "Defender": 1, "Midfielder": 2, "Attacker": 3}.get(item.position, 9),
            item.position_slot,
        ),
    )

    return {
        "id": team.id,
        "formation": team.formation,
        "captain_player_id": team.captain_player_id,
        "points": team.points or 0,
        "is_locked": bool(team.is_locked),
        "transfer_window_key": getattr(team, "transfer_window_key", None),
        "transfers_used": getattr(team, "transfers_used", 0) or 0,
        "transfer_penalty_points": getattr(team, "transfer_penalty_points", 0) or 0,
        "players": [
            {
                "position_slot": item.position_slot,
                "position": item.position,
                "position_label": FANTASY_POSITION_LABELS.get(item.position, item.position),
                "is_captain": bool(item.is_captain),
                "is_starter": bool(getattr(item, "is_starter", True)),
                "bench_order": getattr(item, "bench_order", None),
                "points": item.points or 0,
                "player": _serialize_fantasy_player(item.player),
            }
            for item in team_players
        ],
    }


def _fantasy_rules_payload(db: Session | None = None) -> dict:
    """Return FIFA-style fantasy rules adapted for WC2026 Mini App."""
    round_state = _fantasy_round_state(db) if db is not None else {
        "key": "group_1",
        "title": "1-й тур группового этапа",
        "deadline_at": None,
        "is_locked": is_tournament_started(),
        "free_transfers": None,
        "extra_transfer_penalty": FANTASY_EXTRA_TRANSFER_PENALTY,
        "max_from_one_team": 3,
        "category_limits": FANTASY_CATEGORY_LIMITS_GROUP,
        "category_limits_enabled": True,
    }
    category_limits = round_state.get("category_limits") or {}
    max_from_one_team = round_state.get("max_from_one_team") or 3

    return {
        "formation": FANTASY_FORMATION,
        "squad_size": 15,
        "starters_size": 11,
        "squad_positions": FANTASY_SQUAD_POSITION_LIMITS,
        "starter_positions": FANTASY_STARTER_POSITION_LIMITS,
        "position_labels": FANTASY_POSITION_LABELS,
        "max_from_one_team": max_from_one_team,
        "category_limits": category_limits,
        "round_state": round_state,
        "categories": [
            {"id": 1, "title": "Элита", "range": "ФИФА 1–12", "limit": category_limits.get(1), "enabled": 1 in category_limits},
            {"id": 2, "title": "Сильные претенденты", "range": "ФИФА 13–24", "limit": category_limits.get(2), "enabled": 2 in category_limits},
            {"id": 3, "title": "Середина", "range": "ФИФА 25–36", "limit": category_limits.get(3), "enabled": 3 in category_limits},
            {"id": 4, "title": "Аутсайдеры и дебютанты", "range": "ФИФА 37–48", "limit": category_limits.get(4), "enabled": 4 in category_limits},
        ],
        "transfer_rules": [
            {"stage": "До 1-го тура", "free": "без ограничений", "penalty": 0},
            {"stage": "До 2-го тура", "free": 2, "penalty": -3},
            {"stage": "До 3-го тура", "free": 2, "penalty": -3},
            {"stage": "До 1/8", "free": "без ограничений", "penalty": 0},
            {"stage": "До 1/4", "free": 4, "penalty": -3},
            {"stage": "До 1/2", "free": 5, "penalty": -3},
            {"stage": "Перед финалом", "free": 6, "penalty": -3},
        ],
        "scoring": [
            {"title": "Выход на поле", "description": "игрок сыграл в матче", "points": 1, "type": "plus"},
            {"title": "60+ минут", "description": "игрок провел на поле 60 минут и больше", "points": 1, "type": "plus"},
            {"title": "Гол вратаря", "description": "ВР забил гол", "points": 9, "type": "plus"},
            {"title": "Гол защитника", "description": "ЗЩ забил гол", "points": 7, "type": "plus"},
            {"title": "Гол полузащитника", "description": "ПЗ забил гол", "points": 5, "type": "plus"},
            {"title": "Гол нападающего", "description": "НП забил гол", "points": 5, "type": "plus"},
            {"title": "Голевая передача", "description": "ассист", "points": 3, "type": "plus"},
            {"title": "Сухой матч", "description": "ВР или ЗЩ, 60+ минут", "points": 5, "type": "plus"},
            {"title": "Сухой матч ПЗ", "description": "ПЗ, 60+ минут", "points": 1, "type": "plus"},
            {"title": "3 сейва", "description": "ВР: каждые 3 сейва", "points": 1, "type": "plus"},
            {"title": "Отбитый пенальти", "description": "ВР отбил пенальти", "points": 3, "type": "plus"},
            {"title": "Отборы", "description": "ПЗ: каждые 3 отбора", "points": 1, "type": "plus"},
            {"title": "Удары в створ", "description": "НП: каждые 2 удара в створ", "points": 1, "type": "plus"},
            {"title": "Желтая карточка", "description": "предупреждение", "points": -1, "type": "minus"},
            {"title": "Красная карточка", "description": "удаление", "points": -2, "type": "minus"},
            {"title": "Автогол", "description": "гол в свои ворота", "points": -2, "type": "minus"},
            {"title": "Нереализованный пенальти", "description": "игрок не забил пенальти", "points": -2, "type": "minus"},
        ],
        "detailed_rules": [
            "Состав: 15 игроков — 2 ВР, 5 ЗЩ, 5 ПЗ, 3 НП. В основе 11 игроков по схеме 4-3-3.",
            "Игроки скамейки тоже набирают очки, но в общий счет идут только очки основы и ручные/автоматические замены по правилам тура.",
            "Капитана можно менять внутри тура только на игрока, который еще не сыграл. Если капитан заменен, двойные очки предыдущего капитана теряются.",
            "Перед 1-м туром и 1/8 финала трансферы бесплатные без ограничений. Перед 2-м и 3-м турами — 2 бесплатных трансфера, перед 1/4 — 4, перед 1/2 — 5, перед финалом — 6.",
            "Каждый лишний трансфер дает штраф -3 очка.",
            "Бюджета игроков в нашей версии нет.",
            "Лимит сборных: групповой этап — до 3 игроков из одной сборной, 1/8 — до 4, 1/4 — до 5, 1/2 — до 6, финал — до 8.",
            "Лимиты по категориям FIFA действуют на группе и 1/8; с 1/4 ограничения Г1/Г2/Г3/Г4 снимаются.",
        ],
        "captain": {
            "enabled": True,
            "multiplier": 2,
            "description": "Очки капитана удваиваются.",
        },
        "is_locked": bool(round_state.get("is_locked")),
    }

def _fantasy_team_summary(team: FantasyTeam | None) -> dict:
    """Build fantasy progress summary."""
    if not team:
        return {
            "selected": 0,
            "total": 15,
            "progress": "0/15",
            "points": 0,
            "captain_selected": False,
            "complete": False,
        }

    selected = len(team.players)
    return {
        "selected": selected,
        "total": 15,
        "progress": f"{selected}/15",
        "points": team.points or 0,
        "captain_selected": team.captain_player_id is not None,
        "complete": selected == 15 and team.captain_player_id is not None,
    }


def _validate_fantasy_payload(
    players: list[FantasyPlayer],
    starting_player_ids: list[int],
    captain_player_id: int,
    rules: dict,
) -> None:
    """Validate fantasy squad, starting XI and active transfer-window constraints."""
    if len(players) != 15:
        raise HTTPException(status_code=400, detail="В fantasy-команде должно быть ровно 15 игроков.")

    player_ids = [player.id for player in players]

    if len(set(player_ids)) != 15:
        raise HTTPException(status_code=400, detail="Игроки в fantasy-команде не должны повторяться.")

    if len(set(starting_player_ids)) != 11:
        raise HTTPException(status_code=400, detail="В стартовом составе должно быть ровно 11 разных игроков.")

    if not set(starting_player_ids).issubset(set(player_ids)):
        raise HTTPException(status_code=400, detail="Стартовый состав должен состоять из игроков вашей fantasy-команды.")

    if captain_player_id not in starting_player_ids:
        raise HTTPException(status_code=400, detail="Капитан должен быть выбран из стартового состава.")

    position_counts = Counter(player.position for player in players)

    for position, limit in FANTASY_SQUAD_POSITION_LIMITS.items():
        if position_counts.get(position, 0) != limit:
            label = FANTASY_POSITION_LABELS.get(position, position)
            raise HTTPException(
                status_code=400,
                detail=f"В заявке нужно выбрать {limit} игроков позиции {label}.",
            )

    players_by_id = {player.id: player for player in players}
    starter_counts = Counter(players_by_id[player_id].position for player_id in starting_player_ids)

    for position, limit in FANTASY_STARTER_POSITION_LIMITS.items():
        if starter_counts.get(position, 0) != limit:
            label = FANTASY_POSITION_LABELS.get(position, position)
            raise HTTPException(
                status_code=400,
                detail=f"Для схемы {FANTASY_FORMATION} в основе нужно выбрать {limit} игроков позиции {label}.",
            )

    max_from_one_team = rules.get("max_from_one_team") or 3
    team_counts = Counter(player.team_display_name for player in players)
    too_many_team = [team for team, count in team_counts.items() if count > max_from_one_team]

    if too_many_team:
        raise HTTPException(
            status_code=400,
            detail=f"На текущей стадии из одной сборной можно взять не больше {max_from_one_team} игроков: {too_many_team[0]}.",
        )

    category_limits = rules.get("category_limits") or {}
    starter_category_counts = Counter(players_by_id[player_id].fifa_category for player_id in starting_player_ids)

    for category, limit in category_limits.items():
        if starter_category_counts.get(int(category), 0) > limit:
            raise HTTPException(
                status_code=400,
                detail=f"В основе из категории «{_fantasy_category_title(int(category))}» можно выбрать не больше {limit} игроков.",
            )


@router.get("/fantasy/rules")
def get_fantasy_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return fantasy rules and scoring."""
    return _fantasy_rules_payload(db)


@router.get("/fantasy/players")
def get_fantasy_players(
    position: str | None = Query(default=None),
    team: str | None = Query(default=None),
    category: int | None = Query(default=None, ge=1, le=4),
    q: str | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return fantasy players with filters."""
    query = db.query(FantasyPlayer).filter(
        FantasyPlayer.tournament_code == TOURNAMENT_CODE,
        FantasyPlayer.is_active == True,
    )

    if position:
        query = query.filter(FantasyPlayer.position == position)

    if team:
        query = query.filter(FantasyPlayer.team_display_name == team)

    if category:
        query = query.filter(FantasyPlayer.fifa_category == category)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(FantasyPlayer.player_name.ilike(like))

    players = (
        query
        .order_by(
            FantasyPlayer.fifa_category.asc(),
            FantasyPlayer.team_display_name.asc(),
            FantasyPlayer.position.asc(),
            FantasyPlayer.player_name.asc(),
        )
        .limit(limit)
        .all()
    )

    teams = [
        {"name": name, "flag": get_team_flag(name)}
        for (name,) in db.query(FantasyPlayer.team_display_name)
        .filter(FantasyPlayer.tournament_code == TOURNAMENT_CODE, FantasyPlayer.is_active == True)
        .distinct()
        .order_by(FantasyPlayer.team_display_name.asc())
        .all()
    ]

    return {
        "players": [_serialize_fantasy_player(player) for player in players],
        "teams": teams,
        "rules": _fantasy_rules_payload(db),
    }


@router.get("/fantasy/team/me")
def get_my_fantasy_team(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current user's fantasy team."""
    team = (
        db.query(FantasyTeam)
        .filter(
            FantasyTeam.user_id == current_user.id,
            FantasyTeam.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    return {
        "team": _serialize_fantasy_team(team),
        "summary": _fantasy_team_summary(team),
        "rules": _fantasy_rules_payload(db),
    }


@router.post("/fantasy/team")
def save_my_fantasy_team(
    payload: FantasyTeamPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Save current user's fantasy squad and apply transfer-window rules."""
    rules = _fantasy_rules_payload(db)
    round_state = rules["round_state"]

    if round_state.get("is_locked"):
        raise HTTPException(status_code=400, detail="Fantasy-команду уже нельзя менять: дедлайны турнира прошли.")

    if payload.formation != FANTASY_FORMATION:
        raise HTTPException(status_code=400, detail=f"Пока поддерживается только схема {FANTASY_FORMATION}.")

    players = (
        db.query(FantasyPlayer)
        .filter(
            FantasyPlayer.tournament_code == TOURNAMENT_CODE,
            FantasyPlayer.is_active == True,
            FantasyPlayer.id.in_(payload.player_ids),
        )
        .all()
    )

    if len(players) != len(set(payload.player_ids)):
        raise HTTPException(status_code=400, detail="Не все выбранные игроки найдены в fantasy-списке.")

    _validate_fantasy_payload(players, payload.starting_player_ids, payload.captain_player_id, rules)

    team = (
        db.query(FantasyTeam)
        .filter(
            FantasyTeam.user_id == current_user.id,
            FantasyTeam.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    new_ids = {int(player_id) for player_id in payload.player_ids}
    window_key = round_state["key"]
    free_transfers = round_state.get("free_transfers")
    transfers_used = 0
    transfer_penalty = 0

    if not team:
        team = FantasyTeam(
            user_id=current_user.id,
            tournament_code=TOURNAMENT_CODE,
            formation=payload.formation,
        )
        db.add(team)
        db.flush()
        baseline_ids = set(new_ids)
    else:
        current_ids = {item.player_id for item in team.players}
        if team.transfer_window_key != window_key:
            baseline_ids = set(current_ids)
        else:
            baseline_ids = _load_baseline_ids(getattr(team, "transfer_baseline_player_ids", None)) or set(current_ids)

        if free_transfers is not None and baseline_ids:
            transfers_used = len(new_ids - baseline_ids)
            transfer_penalty = max(0, transfers_used - int(free_transfers)) * FANTASY_EXTRA_TRANSFER_PENALTY

    team.formation = payload.formation
    team.captain_player_id = payload.captain_player_id
    team.transfer_window_key = window_key
    team.transfer_baseline_player_ids = json.dumps(sorted(baseline_ids))
    team.transfers_used = transfers_used
    team.transfer_penalty_points = transfer_penalty
    team.updated_at = datetime.now(timezone.utc)

    db.query(FantasyTeamPlayer).filter(FantasyTeamPlayer.fantasy_team_id == team.id).delete()

    players_by_id = {player.id: player for player in players}
    starter_id_set = {int(player_id) for player_id in payload.starting_player_ids}
    position_indexes: dict[str, int] = {}
    order = {"Goalkeeper": 0, "Defender": 1, "Midfielder": 2, "Attacker": 3}

    starter_ordered_ids = list(payload.starting_player_ids)
    bench_ordered_ids = [player_id for player_id in payload.player_ids if player_id not in starter_id_set]
    ordered_ids = starter_ordered_ids + bench_ordered_ids

    for player_id in ordered_ids:
        player = players_by_id[int(player_id)]
        is_starter = player.id in starter_id_set
        position_indexes[player.position] = position_indexes.get(player.position, 0) + 1
        slot_prefix = FANTASY_POSITION_LABELS.get(player.position, player.position)
        slot = f"{slot_prefix}{position_indexes[player.position]}" if is_starter else f"ЗАП{len([x for x in ordered_ids[:ordered_ids.index(player_id)] if x not in starter_id_set]) + 1}"
        db.add(
            FantasyTeamPlayer(
                fantasy_team_id=team.id,
                player_id=player.id,
                position_slot=slot,
                position=player.position,
                is_captain=player.id == payload.captain_player_id,
                is_starter=is_starter,
                bench_order=None if is_starter else bench_ordered_ids.index(player.id) + 1,
            )
        )

    db.commit()
    db.refresh(team)

    return {
        "team": _serialize_fantasy_team(team),
        "summary": _fantasy_team_summary(team),
        "rules": _fantasy_rules_payload(db),
    }


@router.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current user's Mini App profile, stats and achievements."""
    predictions = (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id)
        .all()
    )

    future_matches = get_all_available_matches(db, limit=1000)
    predictions_by_future_match = _prediction_by_match_id(db, current_user, future_matches)

    missing_count = sum(
        1
        for match in future_matches
        if match.id not in predictions_by_future_match
    )
    editable_count = sum(
        1
        for match in future_matches
        if match.id in predictions_by_future_match
    )

    tournament_prediction = (
        db.query(TournamentPrediction)
        .filter(
            TournamentPrediction.user_id == current_user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    table_rows = build_table_rows(db)
    rank = None
    total_points = 0
    match_points = 0
    tournament_points = 0

    for index, row in enumerate(table_rows, start=1):
        if row["name"] == current_user.display_name:
            rank = index
            total_points = row["points"]
            match_points = row["match_points"]
            tournament_points = row["tournament_points"]
            break

    exact_scores = sum(1 for prediction in predictions if prediction.score_points == 3)
    outcomes = sum(1 for prediction in predictions if prediction.score_points == 1)
    advancement_plus = sum(1 for prediction in predictions if prediction.advancement_points == 1)
    advancement_minus = sum(1 for prediction in predictions if prediction.advancement_points == -1)

    total_predictions = len(predictions)
    favorite_score = _favorite_score(predictions)
    status_text = _profile_status(total_points, exact_scores, total_predictions, missing_count)

    return {
        "user": {
            "id": current_user.id,
            "telegram_id": current_user.telegram_id,
            "username": current_user.username,
            "display_name": current_user.display_name,
            "initials": "".join(part[:1] for part in current_user.display_name.split()[:2]).upper() or "ОП",
            "is_admin": bool(current_user.is_admin),
            "created_at": _ensure_utc(current_user.created_at).isoformat() if current_user.created_at else None,
        },
        "summary": {
            "rank": rank,
            "status": status_text,
            "points": total_points,
            "match_points": match_points,
            "tournament_points": tournament_points,
            "fantasy_points": 0,
            "total_predictions": total_predictions,
            "missing_predictions": missing_count,
            "editable_predictions": editable_count,
            "exact_scores": exact_scores,
            "outcomes": outcomes,
            "advancement_plus": advancement_plus,
            "advancement_minus": advancement_minus,
            "favorite_score": favorite_score,
        },
        "points_breakdown": [
            {"key": "matches", "title": "Прогнозы", "points": match_points, "icon": "ball"},
            {"key": "tournament", "title": "Турнир", "points": tournament_points, "icon": "cup"},
            {"key": "fantasy", "title": "Fantasy-команда", "points": 0, "icon": "team"},
        ],
        "tournament_prediction": _serialize_tournament_prediction(tournament_prediction) if tournament_prediction else None,
        "badges": _profile_badges(
            exact_scores=exact_scores,
            outcomes=outcomes,
            total_predictions=total_predictions,
            missing_count=missing_count,
            tournament_prediction=tournament_prediction,
            rank=rank,
        ),
    }


@router.get("/facts/random")
def get_random_fact(
    category: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a random active World Cup fact."""
    query = db.query(WorldCupFact).filter(WorldCupFact.is_active == True)

    if category and category != "any":
        query = query.filter(WorldCupFact.category == category)

    facts = query.all()

    if not facts:
        raise HTTPException(status_code=404, detail="Facts not found")

    fact = random.choice(facts)

    return {
        "fact": {
            "id": fact.id,
            "title": fact.title,
            "text": fact.fact_text,
            "category": fact.category,
            "tournament_year": fact.tournament_year,
            "spicy_comment": fact.spicy_comment,
        }
    }


@router.get("/quiz/random")
def get_random_quiz(
    category: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a random active quiz question."""
    query = db.query(QuizQuestion).filter(QuizQuestion.is_active == True)

    if category and category != "any":
        query = query.filter(QuizQuestion.category == category)

    questions = query.all()

    if not questions:
        raise HTTPException(status_code=404, detail="Quiz questions not found")

    question = random.choice(questions)

    return {
        "question": {
            "id": question.id,
            "text": question.question_text,
            "options": {
                "A": question.option_a,
                "B": question.option_b,
                "C": question.option_c,
                "D": question.option_d,
            },
        }
    }


@router.post("/quiz/answer")
def save_quiz_answer(
    payload: QuizAnswerPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Save a quick quiz answer and reveal whether it is correct."""
    selected_option = payload.selected_option.upper().strip()

    if selected_option not in {"A", "B", "C", "D"}:
        raise HTTPException(status_code=400, detail="Invalid option")

    question = db.query(QuizQuestion).filter(QuizQuestion.id == payload.question_id).first()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    is_correct = selected_option == question.correct_option.upper()

    answer = QuizAnswer(
        quiz_question_id=question.id,
        user_id=current_user.id,
        telegram_id=current_user.telegram_id,
        selected_option=selected_option,
        is_correct=is_correct,
    )

    db.add(answer)
    db.commit()

    options = {
        "A": question.option_a,
        "B": question.option_b,
        "C": question.option_c,
        "D": question.option_d,
    }

    return {
        "ok": True,
        "is_correct": is_correct,
        "correct_option": question.correct_option.upper(),
        "correct_text": options.get(question.correct_option.upper()),
        "explanation": question.explanation,
    }


@router.get("/archive/random")
def get_random_archive_card(
    card_type: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a random public archive card."""
    query = db.query(HistoricalArchiveCard).filter(
        HistoricalArchiveCard.is_active == True,
        HistoricalArchiveCard.is_public == True,
    )

    if card_type and card_type != "any":
        query = query.filter(HistoricalArchiveCard.card_type == card_type)

    cards = query.all()

    if not cards:
        raise HTTPException(status_code=404, detail="Archive cards not found")

    card = random.choice(cards)

    return {
        "card": {
            "id": card.id,
            "title": card.title,
            "text": card.text,
            "card_type": card.card_type,
            "tournament_code": card.tournament_code,
            "related_name": card.related_name,
        }
    }


def _empty_group_row(team_name: str, api_name: str | None = None) -> dict:
    """Create an empty group standings row for a national team."""
    display_name = get_team_name_ru(team_name)

    return {
        "team": display_name,
        "flag": get_team_flag(display_name, api_name),
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
        "points": 0,
    }


def _apply_group_match_result(row_home: dict, row_away: dict, match: Match) -> None:
    """Apply a finished group-stage match result to two standings rows."""
    if match.score_home is None or match.score_away is None:
        return

    home_goals = int(match.score_home)
    away_goals = int(match.score_away)

    row_home["played"] += 1
    row_away["played"] += 1

    row_home["goals_for"] += home_goals
    row_home["goals_against"] += away_goals
    row_home["goal_difference"] = row_home["goals_for"] - row_home["goals_against"]

    row_away["goals_for"] += away_goals
    row_away["goals_against"] += home_goals
    row_away["goal_difference"] = row_away["goals_for"] - row_away["goals_against"]

    if home_goals > away_goals:
        row_home["wins"] += 1
        row_home["points"] += 3
        row_away["losses"] += 1
    elif home_goals < away_goals:
        row_away["wins"] += 1
        row_away["points"] += 3
        row_home["losses"] += 1
    else:
        row_home["draws"] += 1
        row_away["draws"] += 1
        row_home["points"] += 1
        row_away["points"] += 1


def _prediction_distribution(db: Session, match: Match) -> dict:
    """Return aggregated user prediction distribution for a match."""
    predictions = db.query(Prediction).filter(Prediction.match_id == match.id).all()
    total = len(predictions)

    home = 0
    draw = 0
    away = 0

    for prediction in predictions:
        if prediction.pred_home > prediction.pred_away:
            home += 1
        elif prediction.pred_home < prediction.pred_away:
            away += 1
        else:
            draw += 1

    def percent(value: int) -> int:
        if total <= 0:
            return 0
        return round(value * 100 / total)

    return {
        "total": total,
        "home": home,
        "draw": draw,
        "away": away,
        "home_percent": percent(home),
        "draw_percent": percent(draw),
        "away_percent": percent(away),
    }


def _serialize_match_center_match(
    db: Session,
    match: Match,
    user_prediction: Prediction | None = None,
) -> dict:
    """Serialize a match card for Mini App 2.0 match center."""
    payload = _serialize_match(match, user_prediction)
    payload["prediction_distribution"] = _prediction_distribution(db, match)
    payload["fifa_match_no"] = match.fifa_match_no
    payload["status_short"] = match.status_short
    payload["status_long"] = match.status_long
    payload["day_key"] = _ensure_utc(match.starts_at).date().isoformat()
    return payload


def _build_group_standings(db: Session) -> list[dict]:
    """Build group standings for all WC2026 groups from stored results."""
    group_matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.group_code.isnot(None),
        )
        .order_by(Match.group_code.asc(), Match.starts_at.asc())
        .all()
    )

    groups: dict[str, dict[str, dict]] = {}

    for match in group_matches:
        group_code = str(match.group_code or "").strip()

        if not group_code:
            continue

        if group_code not in groups:
            groups[group_code] = {}

        for team_name, api_name in [
            (match.home_team, getattr(match, "home_team_api_name", None)),
            (match.away_team, getattr(match, "away_team_api_name", None)),
        ]:
            if not team_name or team_name == "TBD":
                continue

            display_name = get_team_name_ru(team_name)

            if display_name not in groups[group_code]:
                groups[group_code][display_name] = _empty_group_row(team_name, api_name)

        if bool(match.is_finished):
            home_name = get_team_name_ru(match.home_team)
            away_name = get_team_name_ru(match.away_team)

            if home_name in groups[group_code] and away_name in groups[group_code]:
                _apply_group_match_result(
                    groups[group_code][home_name],
                    groups[group_code][away_name],
                    match,
                )

    result = []

    for group_code in sorted(groups):
        rows = list(groups[group_code].values())
        rows.sort(
            key=lambda row: (
                row["points"],
                row["goal_difference"],
                row["goals_for"],
                row["team"],
            ),
            reverse=True,
        )

        for index, row in enumerate(rows, start=1):
            row["rank"] = index
            row["qualification_zone"] = (
                "direct" if index <= 2 else "playoff" if index == 3 else "out"
            )

        result.append(
            {
                "group_code": group_code,
                "rows": rows,
                "matches_played": sum(row["played"] for row in rows) // 2,
            }
        )

    return result


@router.get("/match-center")
def get_match_center(
    scope: str = Query(default="all", pattern="^(all|results)$"),
    group_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return Mini App 2.0 match center data with filters and standings."""
    query = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.asc())
    )

    if group_code:
        query = query.filter(Match.group_code == group_code)

    if scope == "results":
        query = query.filter(Match.is_finished == True)

    matches = query.all()
    predictions_by_match = _prediction_by_match_id(db, current_user, matches)

    all_group_standings = _build_group_standings(db)
    selected_group_standings = (
        [
            group
            for group in all_group_standings
            if not group_code or group["group_code"] == group_code
        ]
    )

    groups = [
        {
            "group_code": group["group_code"],
            "teams_count": len(group["rows"]),
            "matches_played": group["matches_played"],
        }
        for group in all_group_standings
    ]

    return {
        "filters": {
            "scope": scope,
            "group_code": group_code,
        },
        "groups": groups,
        "standings": selected_group_standings,
        "matches": [
            _serialize_match_center_match(db, match, predictions_by_match.get(match.id))
            for match in matches
        ],
    }
