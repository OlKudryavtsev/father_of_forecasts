"""Helpers for final tournament-prediction scoring.

The admin result can be stored in Russian or provider/API English names, while
user predictions are stored as display strings. Keep rating/tournament cards
scored from the final result dynamically so old zero values in
``tournament_predictions`` do not make the finished leaderboard wrong.
"""
from __future__ import annotations

from typing import Any
import os

from sqlalchemy.orm import Session

from app.models import Match, TournamentPrediction, TournamentResult

TOURNAMENT_CODE = os.getenv("TOURNAMENT_CODE", "wc2026")
from app.scoring import score_tournament_prediction
from app.team_names import get_team_name_ru


def _stage_key(match: Match) -> str:
    stage = str(getattr(match, "stage", "") or "").lower()
    raw = f"{getattr(match, 'match_round', '') or ''} {getattr(match, 'api_league_round', '') or ''}".lower()
    if (
        stage in {"third_place", "bronze", "third"}
        or "third" in raw
        or "3rd" in raw
        or "bronze" in raw
        or ("3" in raw and "мест" in raw)
    ):
        return "third_place"
    if stage == "final" or "final" in raw or "финал" in raw:
        return "final"
    return stage


def _winner_and_loser(match: Match) -> tuple[str | None, str | None]:
    home = get_team_name_ru(match.home_team)
    away = get_team_name_ru(match.away_team)
    winner_side = str(getattr(match, "winner_side", "") or "").lower()
    if winner_side == "home":
        return home, away
    if winner_side == "away":
        return away, home
    if match.score_home is not None and match.score_away is not None and match.score_home != match.score_away:
        return (home, away) if match.score_home > match.score_away else (away, home)
    return None, None


def _infer_tournament_result_from_matches(db: Session, tournament_code: str = TOURNAMENT_CODE) -> TournamentResult | None:
    """Infer final placements from finished final/bronze matches and scorer cache."""
    matches = (
        db.query(Match)
        .filter(Match.tournament_code == tournament_code, Match.is_finished == True)
        .order_by(Match.starts_at.desc())
        .all()
    )
    final = next((match for match in matches if _stage_key(match) == "final"), None)
    third = next((match for match in matches if _stage_key(match) == "third_place"), None)
    if not final:
        return None
    champion, runner_up = _winner_and_loser(final)
    third_place, _ = _winner_and_loser(third) if third else (None, None)
    if not champion or not runner_up:
        return None

    top_scorer = ""
    try:
        from app.services.tournament_hub import get_top_scorers

        scorers = get_top_scorers(db, refresh=False, limit=1).get("items") or []
        top_scorer = str((scorers[0] or {}).get("name") or "") if scorers else ""
    except Exception:
        top_scorer = ""

    return TournamentResult(
        tournament_code=tournament_code,
        champion=champion,
        runner_up=runner_up,
        third_place=third_place or "",
        top_scorer=top_scorer,
    )


def infer_tournament_result(db: Session, tournament_code: str = TOURNAMENT_CODE) -> TournamentResult | None:
    """Return saved result, enriched with inferred final/bronze data when needed.

    Older deployments could save an incomplete result or fail to infer the bronze
    match because the provider called it ``3rd Place Playoff``. When that
    happens, keep the explicit admin values that exist but backfill missing
    champion/runner-up/third-place/top-scorer fields from finished official data.
    """
    explicit = db.query(TournamentResult).filter(TournamentResult.tournament_code == tournament_code).first()
    inferred = _infer_tournament_result_from_matches(db, tournament_code)
    if explicit:
        if not inferred:
            return explicit
        return TournamentResult(
            tournament_code=tournament_code,
            champion=explicit.champion or inferred.champion,
            runner_up=explicit.runner_up or inferred.runner_up,
            third_place=explicit.third_place or inferred.third_place,
            top_scorer=explicit.top_scorer or inferred.top_scorer,
        )
    return inferred

def apply_tournament_result_score(
    prediction: TournamentPrediction | None,
    tournament_result: TournamentResult | None,
) -> dict[str, int]:
    """Calculate and place final tournament points on a prediction object."""
    empty = {
        "champion_points": 0,
        "runner_up_points": 0,
        "third_place_points": 0,
        "top_scorer_points": 0,
        "total_points": 0,
    }
    if not prediction:
        return empty
    if not tournament_result:
        return {
            "champion_points": int(prediction.champion_points or 0),
            "runner_up_points": int(prediction.runner_up_points or 0),
            "third_place_points": int(prediction.third_place_points or 0),
            "top_scorer_points": int(prediction.top_scorer_points or 0),
            "total_points": int(prediction.points or 0),
        }

    result = score_tournament_prediction(
        pred_champion=prediction.champion,
        pred_runner_up=prediction.runner_up,
        pred_third_place=prediction.third_place,
        pred_top_scorer=prediction.top_scorer,
        actual_champion=tournament_result.champion,
        actual_runner_up=tournament_result.runner_up,
        actual_third_place=tournament_result.third_place,
        actual_top_scorer=tournament_result.top_scorer,
    )
    prediction.champion_points = int(result["champion_points"] or 0)
    prediction.runner_up_points = int(result["runner_up_points"] or 0)
    prediction.third_place_points = int(result["third_place_points"] or 0)
    prediction.top_scorer_points = int(result["top_scorer_points"] or 0)
    prediction.points = int(result["total_points"] or 0)
    return result


def tournament_result_payload(result: TournamentResult | None) -> dict[str, Any] | None:
    if not result:
        return None
    return {
        "champion": result.champion,
        "runner_up": result.runner_up,
        "third_place": result.third_place,
        "top_scorer": result.top_scorer,
    }
