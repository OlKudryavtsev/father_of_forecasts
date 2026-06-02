"""FastAPI endpoints used by the Telegram Mini App."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import random

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, get_db
from app.models import (
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
    """Return tournament leaderboard with prediction progress for Mini App."""
    rows = build_table_rows(db)

    users_by_name = {
        user.display_name: user
        for user in db.query(User).all()
    }

    for index, row in enumerate(rows, start=1):
        user = users_by_name.get(row["name"])
        tournament_prediction = None

        if user:
            tournament_prediction = (
                db.query(TournamentPrediction)
                .filter(
                    TournamentPrediction.user_id == user.id,
                    TournamentPrediction.tournament_code == TOURNAMENT_CODE,
                )
                .first()
            )

        row["rank"] = index
        row["is_current_user"] = row["name"] == current_user.display_name
        row["match_predictions_count"] = row.get("total_predictions", 0)
        row["tournament_prediction_count"] = 4 if tournament_prediction else 0
        row["tournament_prediction_total"] = 4
        row["tournament_prediction_progress"] = "4/4" if tournament_prediction else "0/4"

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
