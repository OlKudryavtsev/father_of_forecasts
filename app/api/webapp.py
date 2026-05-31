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
    """Return tournament leaderboard."""
    rows = build_table_rows(db)

    for index, row in enumerate(rows, start=1):
        row["rank"] = index
        row["is_current_user"] = row["name"] == current_user.display_name

    return {"rows": rows}


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
