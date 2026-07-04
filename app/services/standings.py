"""Deterministic championship-scenario calculations for a league leaderboard.

The service describes necessary score conditions for a participant to finish
*strictly* first. It deliberately does not invent a single simulated scoreline
for every remaining fixture: conflicting user predictions make that misleading.
Instead, every scenario contains the participant's required point mix and the
maximum extra points that direct competitors may still take.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from typing import Any

from sqlalchemy.orm import Session

from app.models import League, LeagueMember, Match, Prediction, TournamentPrediction, TournamentResult, User
from app.runtime import TOURNAMENT_CODE
from app.services.leagues import league_scoring_start_at
from app.services.matches import is_playoff_match
from app.services.misc import build_table_rows


TOURNAMENT_ITEM_META = (
    ("champion", "champion_points", 15, "🏆 Чемпион"),
    ("runner_up", "runner_up_points", 10, "🥈 Финалист"),
    ("third_place", "third_place_points", 5, "🥉 3-е место"),
    ("top_scorer", "top_scorer_points", 15, "⚽ Бомбардир"),
)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _plural(value: int, one: str, few: str, many: str) -> str:
    value = abs(int(value or 0))
    if 11 <= value % 100 <= 14:
        return many
    if value % 10 == 1:
        return one
    if value % 10 in {2, 3, 4}:
        return few
    return many


def _member_rows(db: Session, league: League) -> list[tuple[LeagueMember, User]]:
    return (
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


def _remaining_matches(db: Session, league: League) -> list[Match]:
    query = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.is_finished.is_(False),
        )
        .order_by(Match.starts_at.asc(), Match.id.asc())
    )
    start_at = _utc(league_scoring_start_at(league))
    if start_at is not None:
        query = query.filter(Match.starts_at >= start_at)
    return query.all()


def _tournament_items(prediction: TournamentPrediction | None, tournament_resolved: bool) -> list[dict[str, Any]]:
    if not prediction or tournament_resolved:
        return []
    items: list[dict[str, Any]] = []
    for key, points_field, points, label in TOURNAMENT_ITEM_META:
        # A stored non-zero value is already part of the current table and must
        # not be counted once more as future potential.
        if int(getattr(prediction, points_field, 0) or 0) > 0:
            continue
        choice = str(getattr(prediction, key, "") or "").strip()
        if not choice:
            continue
        items.append({
            "key": key,
            "points": points,
            "label": label,
            "choice": choice,
            "text": f"{label}: {choice} (+{points})",
        })
    return items


def _participant_potential(
    user_id: int,
    matches: list[Match],
    predictions_by_user_match: dict[tuple[int, int], Prediction],
    tournament_prediction: TournamentPrediction | None,
    tournament_resolved: bool,
    now: datetime,
) -> dict[str, Any]:
    score_slots = 0
    advancement_slots = 0
    missing_open = 0
    match_items: list[dict[str, Any]] = []

    for match in matches:
        prediction = predictions_by_user_match.get((user_id, match.id))
        starts_at = _utc(match.starts_at) or now
        can_submit = starts_at > now
        has_prediction = prediction is not None

        # A fixed prediction may still earn points after kick-off. When no
        # prediction exists, only a future fixture is an available opportunity.
        if has_prediction or can_submit:
            score_slots += 1
            if not has_prediction:
                missing_open += 1
            advancement_available = bool(is_playoff_match(match) and (
                not has_prediction
                or bool(getattr(prediction, "advancement_bet_enabled", False))
                or getattr(prediction, "predicted_advancing_side", None) in {"home", "away"}
            ))
            if advancement_available:
                advancement_slots += 1
            match_items.append({
                "match_id": match.id,
                "label": f"{match.home_team} — {match.away_team}",
                "starts_at": starts_at.isoformat(),
                "is_playoff": bool(is_playoff_match(match)),
                "has_prediction": has_prediction,
                "score_max": 3,
                "advancement_max": 1 if advancement_available else 0,
            })

    tournament_items = _tournament_items(tournament_prediction, tournament_resolved)
    match_max = 3 * score_slots + advancement_slots
    tournament_max = sum(int(item["points"] or 0) for item in tournament_items)
    return {
        "score_slots": score_slots,
        "advancement_slots": advancement_slots,
        "missing_open": missing_open,
        "match_max": match_max,
        "tournament_items": tournament_items,
        "tournament_max": tournament_max,
        "total_max": match_max + tournament_max,
        "match_items": match_items,
    }


def _solve_match_plan(required_points: int, score_slots: int, advancement_slots: int, preference: int = 0) -> dict[str, int] | None:
    """Find a readable exact/outcome/advancement mix for at least required points."""
    required_points = max(0, int(required_points or 0))
    candidates: list[tuple[tuple[int, int, int, int, int], dict[str, int]]] = []
    for exact in range(score_slots + 1):
        for outcomes in range(score_slots - exact + 1):
            for advancement in range(advancement_slots + 1):
                points = exact * 3 + outcomes + advancement
                if points < required_points:
                    continue
                overshoot = points - required_points
                # Rotate the tie-breaker so neighbouring variants do not all
                # read as the same "exact scores only" plan.
                if preference % 3 == 0:
                    complexity = (exact, outcomes, advancement)
                elif preference % 3 == 1:
                    complexity = (-outcomes, exact, advancement)
                else:
                    complexity = (-advancement, exact, outcomes)
                key = (overshoot, *complexity, exact + outcomes + advancement)
                candidates.append((key, {
                    "points": points,
                    "exact": exact,
                    "outcomes": outcomes,
                    "advancement": advancement,
                }))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _tournament_combinations(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    variants: list[list[dict[str, Any]]] = [[]]
    for length in range(1, len(items) + 1):
        variants.extend([list(combo) for combo in combinations(items, length)])
    # Prefer combinations that explain a scenario with less long-term reliance;
    # the caller rotates the order for a varied top-10 result.
    variants.sort(key=lambda combo: (sum(int(item["points"]) for item in combo), len(combo)))
    return variants


def _sample_totals(minimum: int, maximum: int, limit: int) -> list[int]:
    if maximum < minimum:
        return []
    all_values = list(range(minimum, maximum + 1))
    if len(all_values) <= limit:
        return list(reversed(all_values))
    chosen: set[int] = set()
    for index in range(limit):
        ratio = index / max(1, limit - 1)
        chosen.add(round(maximum - (maximum - minimum) * ratio))
    # Keep the hard and the forgiving boundary even with rounding collisions.
    chosen.add(minimum)
    chosen.add(maximum)
    return sorted(chosen, reverse=True)[:limit]


def _scenario_plan_text(plan: dict[str, int], missing_open: int) -> list[str]:
    parts: list[str] = []
    if int(plan.get("exact") or 0):
        value = int(plan["exact"])
        parts.append(f"🎯 {value} {_plural(value, 'точный счёт', 'точных счёта', 'точных счетов')}")
    if int(plan.get("outcomes") or 0):
        value = int(plan["outcomes"])
        parts.append(f"✅ {value} {_plural(value, 'исход', 'исхода', 'исходов')}")
    if int(plan.get("advancement") or 0):
        value = int(plan["advancement"])
        parts.append(f"🟢 {value} {_plural(value, 'проход', 'прохода', 'проходов')}")
    if not parts:
        parts.append("без дополнительных очков за матчи")
    if missing_open:
        parts.append(f"✍️ оформить {missing_open} {_plural(missing_open, 'прогноз', 'прогноза', 'прогнозов')}")
    return parts


def build_standings_scenarios(
    db: Session,
    league: League,
    participant_user_id: int,
    limit: int = 10,
) -> dict[str, Any]:
    """Return up to ``limit`` strict-first-place score scenarios for a member."""
    member_rows = _member_rows(db, league)
    users = {user.id: user for _member, user in member_rows}
    if participant_user_id not in users:
        raise ValueError("Участник не состоит в выбранной лиге")

    table_rows = build_table_rows(db, league_id=league.id)
    rows_by_user = {int(row.get("user_id") or 0): row for row in table_rows}
    target_row = rows_by_user.get(int(participant_user_id))
    if not target_row:
        raise ValueError("Не удалось собрать строку рейтинга участника")

    now = datetime.now(timezone.utc)
    remaining_matches = _remaining_matches(db, league)
    user_ids = list(users)
    match_ids = [match.id for match in remaining_matches]
    predictions = []
    if user_ids and match_ids:
        predictions = (
            db.query(Prediction)
            .filter(Prediction.user_id.in_(user_ids), Prediction.match_id.in_(match_ids))
            .all()
        )
    predictions_by_user_match = {(prediction.user_id, prediction.match_id): prediction for prediction in predictions}

    tournament_predictions = {
        prediction.user_id: prediction
        for prediction in db.query(TournamentPrediction)
        .filter(TournamentPrediction.user_id.in_(user_ids), TournamentPrediction.tournament_code == TOURNAMENT_CODE)
        .all()
    }
    tournament_resolved = (
        db.query(TournamentResult)
        .filter(TournamentResult.tournament_code == TOURNAMENT_CODE)
        .first()
        is not None
    )

    potential_by_user = {
        user_id: _participant_potential(
            user_id=user_id,
            matches=remaining_matches,
            predictions_by_user_match=predictions_by_user_match,
            tournament_prediction=tournament_predictions.get(user_id),
            tournament_resolved=tournament_resolved,
            now=now,
        )
        for user_id in user_ids
    }

    target_current = int(target_row.get("points") or 0)
    target_potential = potential_by_user[participant_user_id]
    target_max_final = target_current + int(target_potential["total_max"] or 0)
    competitors = []
    for row in table_rows:
        user_id = int(row.get("user_id") or 0)
        if not user_id or user_id == participant_user_id:
            continue
        current = int(row.get("points") or 0)
        potential = potential_by_user.get(user_id) or {}
        competitors.append({
            "user_id": user_id,
            "name": row.get("name") or users[user_id].display_name,
            "current_points": current,
            "max_extra": int(potential.get("total_max") or 0),
            "max_final": current + int(potential.get("total_max") or 0),
        })
    competitors.sort(key=lambda item: (-item["current_points"], item["name"].casefold()))

    rank = next((index for index, row in enumerate(table_rows, start=1) if int(row.get("user_id") or 0) == participant_user_id), None)
    leader_current = max((item["current_points"] for item in competitors), default=-1)
    minimum_final = max(target_current, leader_current + 1)

    base_payload = {
        "league": {"id": league.id, "name": league.name},
        "participant": {
            "user_id": participant_user_id,
            "name": users[participant_user_id].display_name,
            "rank": rank,
            "current_points": target_current,
        },
        "remaining": {
            "matches": len(remaining_matches),
            "match_max": int(target_potential["match_max"] or 0),
            "tournament_max": int(target_potential["tournament_max"] or 0),
            "missing_open_predictions": int(target_potential["missing_open"] or 0),
            "max_final_points": target_max_final,
            "tournament_resolved": tournament_resolved,
        },
        "note": (
            "Каждый вариант — набор необходимых условий: выбранный участник должен набрать указанные очки, "
            "а конкуренты не превысить свои лимиты. Это не единая симуляция конкретных счетов матчей."
        ),
        "scenarios": [],
        "is_mathematically_possible": target_max_final > leader_current,
        "elimination_reason": None,
    }

    if not base_payload["is_mathematically_possible"]:
        base_payload["elimination_reason"] = (
            f"Даже максимальный итог — {target_max_final} очк.; для единоличного первого места нужно минимум {leader_current + 1}."
        )
        return base_payload

    combinations_list = _tournament_combinations(target_potential["tournament_items"])
    scenario_totals = _sample_totals(minimum_final, target_max_final, max(1, int(limit or 10)))
    scenarios: list[dict[str, Any]] = []

    for ordinal, final_points in enumerate(scenario_totals, start=1):
        desired_extra = final_points - target_current
        found = None
        ordered_combos = combinations_list[ordinal % len(combinations_list):] + combinations_list[:ordinal % len(combinations_list)] if combinations_list else [[]]
        for combo in ordered_combos:
            tournament_points = sum(int(item["points"] or 0) for item in combo)
            required_match_points = max(0, desired_extra - tournament_points)
            plan = _solve_match_plan(
                required_match_points,
                int(target_potential["score_slots"] or 0),
                int(target_potential["advancement_slots"] or 0),
                preference=ordinal,
            )
            if plan is None:
                continue
            actual_extra = tournament_points + int(plan["points"] or 0)
            actual_final = target_current + actual_extra
            if actual_final <= leader_current:
                continue
            found = (combo, plan, actual_extra, actual_final)
            break
        if not found:
            continue

        combo, plan, actual_extra, actual_final = found
        competitor_limits = []
        for competitor in competitors:
            allowed_extra = actual_final - 1 - competitor["current_points"]
            if competitor["max_extra"] > allowed_extra:
                competitor_limits.append({
                    "user_id": competitor["user_id"],
                    "name": competitor["name"],
                    "current_points": competitor["current_points"],
                    "max_extra_allowed": max(0, allowed_extra),
                    "max_extra": competitor["max_extra"],
                })
        competitor_limits.sort(key=lambda item: (-item["current_points"], item["name"].casefold()))

        scenarios.append({
            "number": len(scenarios) + 1,
            "final_points": actual_final,
            "extra_points": actual_extra,
            "match_points": int(plan["points"] or 0),
            "tournament_points": tournament_points,
            "plan": plan,
            "plan_text": _scenario_plan_text(plan, int(target_potential["missing_open"] or 0)),
            "tournament_conditions": [item["text"] for item in combo],
            "competitor_limits": competitor_limits[:3],
        })

    base_payload["scenarios"] = scenarios
    return base_payload


def format_standings_scenarios_telegram(payload: dict[str, Any], max_variants: int = 10) -> str:
    """Render a compact group-chat report that comfortably fits Telegram."""
    participant = payload.get("participant") or {}
    remaining = payload.get("remaining") or {}
    name = participant.get("name") or "Участник"
    lines = [
        f"🏆 Расклады · {name}",
        "",
        f"Сейчас: #{participant.get('rank') or '—'} · {int(participant.get('current_points') or 0)} очк.",
        f"Осталось: {int(remaining.get('matches') or 0)} матч. · максимум ещё +{int(remaining.get('match_max') or 0)} за матчи"
        + (f" и +{int(remaining.get('tournament_max') or 0)} за долгосрок" if int(remaining.get('tournament_max') or 0) else ""),
    ]
    if not payload.get("is_mathematically_possible"):
        lines.extend(["", "❌ Единоличное 1-е место уже недостижимо.", str(payload.get("elimination_reason") or "")])
        return "\n".join(lines)

    scenarios = list(payload.get("scenarios") or [])[:max_variants]
    if not scenarios:
        lines.extend(["", "Пока не удалось собрать достаточный набор вариантов из доступных прогнозов."])
        return "\n".join(lines)

    lines.extend(["", "Варианты для единоличного 1-го места:"])
    for scenario in scenarios:
        lines.append("")
        lines.append(f"{scenario['number']}. Финиш: {scenario['final_points']} очк. (+{scenario['extra_points']})")
        lines.append("   Нужно: " + " · ".join(scenario.get("plan_text") or []))
        conditions = scenario.get("tournament_conditions") or []
        if conditions:
            lines.append("   Долгосрок: " + "; ".join(conditions))
        limits = scenario.get("competitor_limits") or []
        if limits:
            limits_text = "; ".join(
                f"{item['name']} ≤ +{item['max_extra_allowed']} из +{item['max_extra']}"
                for item in limits
            )
            lines.append("   Конкуренты: " + limits_text)

    lines.extend([
        "",
        "ℹ️ Это необходимые условия по очкам, а не обещание конкретных счётов матчей. Футбол всё ещё способен выбрать самый неудобный сценарий.",
    ])
    text = "\n".join(lines)
    return text[:3900]
