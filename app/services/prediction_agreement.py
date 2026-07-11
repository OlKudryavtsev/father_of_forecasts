"""Pairwise prediction-agreement analytics for Mini App and Telegram bot."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import League, LeagueMember, Match, Prediction, User
from app.constants.categories import PLAYOFF_STAGES
from app.team_names import get_team_name_ru

TOURNAMENT_CODE = "wc2026"


def is_playoff_match(match: Match) -> bool:
    """Return True for knockout matches without importing heavy bot services."""
    return str(getattr(match, "stage", "") or "").lower() in PLAYOFF_STAGES


def _ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_round_number(value: str | None) -> int | None:
    text = str(value or "")
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def prediction_agreement_stage(match: Match) -> dict:
    """Return stable stage metadata for pairwise prediction-agreement analytics."""
    stage = (match.stage or "").lower()
    raw = f"{match.match_round or ''} {match.api_league_round or ''}".lower()

    if stage == "group":
        round_number = _parse_round_number(match.match_round) or _parse_round_number(match.api_league_round) or 1
        key = f"group_{round_number}"
        sort = round_number
        label = f"{round_number} тур"
    elif stage in {"round_of_32", "r32", "round_32", "last_32"} or "1/16" in raw or "round of 32" in raw:
        key, sort, label = "round_of_32", 32, "1/16"
    elif stage in {"round_of_16", "r16", "round_16", "last_16"} or "1/8" in raw or "round of 16" in raw:
        key, sort, label = "round_of_16", 33, "1/8"
    elif stage in {"quarterfinal", "quarter", "quarter-final"} or "1/4" in raw or "quarter" in raw:
        key, sort, label = "quarterfinal", 34, "1/4"
    elif stage in {"semifinal", "semi", "semi-final"} or "1/2" in raw or "semi" in raw:
        key, sort, label = "semifinal", 35, "1/2"
    elif stage == "third_place" or "third" in raw or ("3" in raw and "мест" in raw):
        key, sort, label = "third_place", 36, "3-е место"
    elif stage == "final" or "final" in raw or "финал" in raw:
        key, sort, label = "final", 37, "Финал"
    else:
        key = re.sub(r"[^a-z0-9_]+", "_", stage or raw or "stage").strip("_") or "stage"
        sort = 100
        label = (match.match_round or match.api_league_round or match.stage or "Турнир").strip()

    return {"key": key, "label": label, "sort": sort}


def prediction_agreement_signature(prediction: Prediction, *, include_advancement: bool, match: Match) -> tuple:
    """Return the comparable prediction signature for pairwise agreement."""
    signature = (int(prediction.pred_home), int(prediction.pred_away))
    if include_advancement and is_playoff_match(match):
        side = prediction.predicted_advancing_side if prediction.advancement_bet_enabled else None
        signature = (*signature, side or "")
    return signature


def _advancement_label(prediction: Prediction | None) -> str | None:
    if not prediction or not prediction.advancement_bet_enabled:
        return None
    side = prediction.predicted_advancing_side
    if side == "home":
        return "1-я команда"
    if side == "away":
        return "2-я команда"
    return side or None


def _prediction_text(prediction: Prediction | None, *, match: Match) -> str:
    if not prediction:
        return "—"
    text = f"{prediction.pred_home}:{prediction.pred_away}"
    if is_playoff_match(match):
        advancement = _advancement_label(prediction)
        if advancement:
            text += f" · проход: {advancement}"
    return text


def _match_title(match: Match) -> str:
    return f"{get_team_name_ru(match.home_team)} — {get_team_name_ru(match.away_team)}"


def build_prediction_agreement_analytics(
    db: Session,
    *,
    league: League,
    include_advancement: bool = False,
    stages: Iterable[str] | None = None,
    examples_limit: int = 3,
    include_match_details: bool = True,
) -> dict:
    """Build pairwise analytics for identical predictions inside one league.

    Only matches that already started or were marked as finished are included.
    A pair is compared for a match only when both active league members had
    submitted a prediction before/for that match.
    """
    now = datetime.now(timezone.utc)
    started_matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .filter((Match.starts_at <= now) | (Match.is_finished == True))  # noqa: E712
        .order_by(Match.starts_at.asc(), Match.id.asc())
        .all()
    )

    stage_counts: dict[str, dict] = {}
    match_stage_by_id: dict[int, dict] = {}
    for match in started_matches:
        meta = prediction_agreement_stage(match)
        match_stage_by_id[match.id] = meta
        existing = stage_counts.setdefault(
            meta["key"],
            {"key": meta["key"], "label": meta["label"], "sort": meta["sort"], "count": 0},
        )
        existing["count"] += 1

    selected_stage_keys = {str(item).strip() for item in (stages or []) if str(item).strip()}
    if selected_stage_keys:
        matches = [match for match in started_matches if match_stage_by_id.get(match.id, {}).get("key") in selected_stage_keys]
    else:
        matches = started_matches

    stages_payload = sorted(stage_counts.values(), key=lambda item: (item["sort"], item["label"]))
    selected_keys = selected_stage_keys or {item["key"] for item in stages_payload}
    for item in stages_payload:
        item["selected"] = item["key"] in selected_keys

    member_rows = (
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
    members = [
        {
            "user_id": user.id,
            "display_name": user.display_name,
            "username": user.username,
            "joined_at": _ensure_utc(membership.joined_at) if membership.joined_at else datetime.min.replace(tzinfo=timezone.utc),
        }
        for membership, user in member_rows
    ]
    member_by_id = {item["user_id"]: item for item in members}
    match_ids = [match.id for match in matches]
    predictions = []
    if match_ids and member_by_id:
        predictions = (
            db.query(Prediction)
            .filter(Prediction.match_id.in_(match_ids), Prediction.user_id.in_(list(member_by_id.keys())))
            .all()
        )
    prediction_by_match_user = {(prediction.match_id, prediction.user_id): prediction for prediction in predictions}

    pairs: list[dict] = []
    for left_index, left in enumerate(members):
        for right in members[left_index + 1:]:
            compared = 0
            same = 0
            same_score = 0
            same_advancement = 0
            examples: list[dict] = []
            match_details: list[dict] = []
            for match in matches:
                match_start = _ensure_utc(match.starts_at)
                if left["joined_at"] > match_start or right["joined_at"] > match_start:
                    continue
                left_prediction = prediction_by_match_user.get((match.id, left["user_id"]))
                right_prediction = prediction_by_match_user.get((match.id, right["user_id"]))
                if not left_prediction or not right_prediction:
                    continue

                compared += 1
                score_equal = left_prediction.pred_home == right_prediction.pred_home and left_prediction.pred_away == right_prediction.pred_away
                if score_equal:
                    same_score += 1

                if is_playoff_match(match):
                    left_side = left_prediction.predicted_advancing_side if left_prediction.advancement_bet_enabled else None
                    right_side = right_prediction.predicted_advancing_side if right_prediction.advancement_bet_enabled else None
                    advancement_equal = bool(left_side and right_side and left_side == right_side)
                else:
                    left_side = right_side = None
                    advancement_equal = True
                if is_playoff_match(match) and advancement_equal:
                    same_advancement += 1

                signatures_equal = prediction_agreement_signature(left_prediction, include_advancement=include_advancement, match=match) == prediction_agreement_signature(right_prediction, include_advancement=include_advancement, match=match)
                stage_label = match_stage_by_id.get(match.id, {}).get("label") or prediction_agreement_stage(match)["label"]
                if signatures_equal:
                    same += 1
                    if len(examples) < examples_limit:
                        examples.append({
                            "match_id": match.id,
                            "home_team": get_team_name_ru(match.home_team),
                            "away_team": get_team_name_ru(match.away_team),
                            "score": f"{left_prediction.pred_home}:{left_prediction.pred_away}",
                            "stage": stage_label,
                        })
                if include_match_details:
                    match_details.append({
                        "match_id": match.id,
                        "home_team": get_team_name_ru(match.home_team),
                        "away_team": get_team_name_ru(match.away_team),
                        "match_title": _match_title(match),
                        "stage": stage_label,
                        "same": bool(signatures_equal),
                        "same_score": bool(score_equal),
                        "same_advancement": bool(advancement_equal) if is_playoff_match(match) else None,
                        "user1_prediction": _prediction_text(left_prediction, match=match),
                        "user2_prediction": _prediction_text(right_prediction, match=match),
                        "user1_score": f"{left_prediction.pred_home}:{left_prediction.pred_away}",
                        "user2_score": f"{right_prediction.pred_home}:{right_prediction.pred_away}",
                        "user1_advancement": _advancement_label(left_prediction),
                        "user2_advancement": _advancement_label(right_prediction),
                    })
            if compared:
                pairs.append({
                    "user1_id": left["user_id"],
                    "user1": left["display_name"],
                    "user2_id": right["user_id"],
                    "user2": right["display_name"],
                    "same_count": same,
                    "compared_count": compared,
                    "same_percent": round((same / compared) * 100, 1) if compared else 0,
                    "same_score_count": same_score,
                    "same_advancement_count": same_advancement,
                    "examples": examples,
                    "matches": match_details,
                })

    pairs.sort(key=lambda item: (-item["same_count"], -item["same_percent"], -item["compared_count"], item["user1"], item["user2"]))

    return {
        "league": {
            "id": league.id,
            "name": league.name,
        },
        "include_advancement": include_advancement,
        "stages": stages_payload,
        "summary": {
            "matches_count": len(matches),
            "started_matches_count": len(started_matches),
            "participants_count": len(members),
            "pairs_count": len(pairs),
        },
        "pairs": pairs,
    }


def format_prediction_agreement_top_text(payload: dict, *, limit: int = 10) -> str:
    """Format top pairwise agreement analytics for Telegram."""
    league_name = payload.get("league", {}).get("name") or "лига"
    pairs = list(payload.get("pairs") or [])[:limit]
    summary = payload.get("summary") or {}
    mode = "с учётом прохода" if payload.get("include_advancement") else "без учёта прохода"

    lines = [
        "🧠 Топ пар с одинаковыми прогнозами",
        f"Лига: {league_name}",
        f"Режим: {mode}",
        f"Матчей в выборке: {summary.get('matches_count', 0)} · пар: {summary.get('pairs_count', 0)}",
        "",
    ]
    if not pairs:
        lines.append("Пока нет пар для сравнения: нужны начавшиеся матчи, где оба участника сделали прогноз.")
        return "\n".join(lines)

    for index, pair in enumerate(pairs, start=1):
        examples = pair.get("examples") or []
        example_text = ""
        if examples:
            example_text = "\n   Примеры: " + "; ".join(
                f"{item.get('home_team')} — {item.get('away_team')} {item.get('score')}"
                for item in examples[:2]
            )
        lines.append(
            f"{index}. {pair.get('user1')} × {pair.get('user2')} — "
            f"{pair.get('same_count')}/{pair.get('compared_count')} ({pair.get('same_percent')}%)"
            f"{example_text}"
        )
    return "\n".join(lines)
