"""Transparent championship-scenario calculations for a league leaderboard.

The service works with the fixed final part of the WC-2026 bracket: eight
round-of-16 fixtures, four quarter-finals, two semi-finals, a third-place match
and the final. It never treats an uncreated future fixture as absent merely
because its teams are not known yet. Long-term tournament picks are included
only while they are still mathematically alive according to completed official
matches.
"""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import os
from random import Random
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.models import FatherMatchPrediction, League, LeagueMember, LeagueWinModelCache, Match, Prediction, TournamentPrediction, TournamentResult, User
from app.runtime import TOURNAMENT_CODE
from app.services.leagues import league_scoring_start_at
from app.services.misc import build_table_rows
from app.services.tournament_hub import get_top_scorers, resolve_player_by_name
from app.team_names import get_team_name_ru
from app.fifa_rankings import FifaRankingsStore

try:
    from app.services.tournament_forecast import load_father_tournament_forecast
except ImportError:  # pragma: no cover - defensive fallback for partial deployments
    load_father_tournament_forecast = None


# The user-facing competition includes the bronze-medal fixture: the full
# remaining knockout schedule is 8 + 4 + 2 + 1 + 1 = 16 matches.
PLAYOFF_PLAN: tuple[tuple[str, int, str], ...] = (
    ("round_of_16", 8, "1/8 финала"),
    ("quarterfinal", 4, "1/4 финала"),
    ("semifinal", 2, "1/2 финала"),
    ("third_place", 1, "матч за 3-е место"),
    ("final", 1, "финал"),
)
PLAYOFF_STAGE_COUNTS = {stage: count for stage, count, _label in PLAYOFF_PLAN}
PLAYOFF_STAGE_LABELS = {stage: label for stage, _count, label in PLAYOFF_PLAN}

TOURNAMENT_ITEM_META = (
    ("champion", "champion_points", 15, "🏆 Чемпион"),
    ("runner_up", "runner_up_points", 10, "🥈 Финалист"),
    ("third_place", "third_place_points", 5, "🥉 3-е место"),
    ("top_scorer", "top_scorer_points", 15, "⚽ Бомбардир"),
)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _plural(value: int, one: str, few: str, many: str) -> str:
    value = abs(int(value or 0))
    if 11 <= value % 100 <= 14:
        return many
    if value % 10 == 1:
        return one
    if value % 10 in {2, 3, 4}:
        return few
    return many


def _normalized_stage(match: Match) -> str:
    """Normalize both local and provider stage names to bracket stages."""
    raw = f"{match.stage or ''} {match.match_round or ''} {match.api_league_round or ''}".casefold()
    if "third" in raw or "3rd" in raw or "3 место" in raw:
        return "third_place"
    # Composite names must be checked before the generic ``final`` suffix.
    if "semi" in raw or "1/2" in raw:
        return "semifinal"
    if "quarter" in raw or "1/4" in raw:
        return "quarterfinal"
    if "round_of_16" in raw or "round of 16" in raw or "1/8" in raw or "r16" in raw:
        return "round_of_16"
    if "round_of_32" in raw or "round of 32" in raw or "1/16" in raw or "r32" in raw:
        return "round_of_32"
    if "final" in raw:
        return "final"
    return str(match.stage or "").casefold()


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


def _league_matches(db: Session, league: League) -> list[Match]:
    """Load tournament fixtures that can affect this league's scoring window."""
    query = db.query(Match).filter(Match.tournament_code == TOURNAMENT_CODE)
    start_at = _utc(league_scoring_start_at(league))
    if start_at is not None:
        query = query.filter(Match.starts_at >= start_at)
    return query.order_by(Match.starts_at.asc(), Match.id.asc()).all()


def _match_side(match: Match, team_name: str) -> str | None:
    normalized = get_team_name_ru(team_name)
    if normalized == get_team_name_ru(match.home_team):
        return "home"
    if normalized == get_team_name_ru(match.away_team):
        return "away"
    return None


def _team_lost_match(match: Match, side: str) -> bool | None:
    """Return a conclusive loss only when official data identifies a winner."""
    winner = str(match.winner_side or "").casefold().strip()
    if winner in {"home", "away"}:
        return winner != side

    # A decisive final score (after extra time when stored) is also conclusive.
    home = match.final_score_home if match.final_score_home is not None else match.score_home
    away = match.final_score_away if match.final_score_away is not None else match.score_away
    if home is None or away is None or int(home) == int(away):
        return None
    return int(home) < int(away) if side == "home" else int(away) < int(home)


def _match_index(matches: list[Match]) -> dict[str, list[tuple[Match, str]]]:
    index: dict[str, list[tuple[Match, str]]] = defaultdict(list)
    for match in matches:
        for side, raw_name in (("home", match.home_team), ("away", match.away_team)):
            name = get_team_name_ru(raw_name)
            if name:
                index[name].append((match, side))
    for entries in index.values():
        entries.sort(key=lambda item: (_utc(item[0].starts_at) or datetime.min.replace(tzinfo=timezone.utc), item[0].id))
    return index


def _team_is_still_alive(team_name: str, match_index: dict[str, list[tuple[Match, str]]], knockout_started: bool) -> bool:
    """Whether a team has not been conclusively eliminated from the tournament."""
    entries = match_index.get(get_team_name_ru(team_name), [])
    knockout_entries = [(match, side) for match, side in entries if _normalized_stage(match) not in {"group", ""}]
    for match, side in knockout_entries:
        if not match.is_finished:
            return True
    for match, side in knockout_entries:
        lost = _team_lost_match(match, side)
        if lost is True:
            return False

    # Once knockout fixtures have begun, a team with a fully completed group
    # stage and no knockout appearance is out. This avoids keeping group-stage
    # eliminations falsely alive in long-term picks.
    group_entries = [(match, side) for match, side in entries if _normalized_stage(match) == "group"]
    if knockout_started and group_entries and all(bool(match.is_finished) for match, _side in group_entries) and not knockout_entries:
        return False
    return True


def _placement_is_alive(
    placement: str,
    team_name: str,
    match_index: dict[str, list[tuple[Match, str]]],
    knockout_started: bool,
) -> bool:
    """Check whether a specific champion/finalist/third-place pick is still possible."""
    entries = match_index.get(get_team_name_ru(team_name), [])
    knockout_entries = [
        (match, side)
        for match, side in entries
        if _normalized_stage(match) not in {"group", ""}
    ]

    if not _team_is_still_alive(team_name, match_index, knockout_started):
        # A semi-final loser remains alive only for the third-place prediction.
        semi_loss = any(
            match.is_finished and _normalized_stage(match) == "semifinal" and _team_lost_match(match, side) is True
            for match, side in knockout_entries
        )
        if placement == "third_place" and semi_loss:
            third_entries = [(match, side) for match, side in knockout_entries if _normalized_stage(match) == "third_place"]
            if not third_entries:
                return True
            return any(not match.is_finished for match, _side in third_entries) or any(
                _team_lost_match(match, side) is False for match, side in third_entries if match.is_finished
            )
        return False

    for match, side in knockout_entries:
        if not match.is_finished:
            continue
        stage = _normalized_stage(match)
        lost = _team_lost_match(match, side)
        if lost is None:
            continue
        if stage == "final":
            if placement == "champion":
                return lost is False
            if placement == "runner_up":
                return lost is True
            return False
        if stage == "third_place":
            return placement == "third_place" and lost is False
        if stage == "semifinal":
            if placement == "third_place":
                if lost is False:
                    return False
                # A loser proceeds to the third-place fixture; evaluate that
                # fixture if it exists, otherwise the forecast is still alive.
                third_entries = [(item, item_side) for item, item_side in knockout_entries if _normalized_stage(item) == "third_place"]
                if not third_entries:
                    return True
                for third_match, third_side in third_entries:
                    if not third_match.is_finished:
                        return True
                    return _team_lost_match(third_match, third_side) is False
                return True
            if lost is True:
                return False
        elif stage in {"round_of_32", "round_of_16", "quarterfinal"} and lost is True:
            return False

    return True


def _canonical_text(value: str | None) -> str:
    return " ".join("".join(ch if ch.isalnum() else " " for ch in str(value or "").casefold()).split())


def _top_scorer_is_alive(
    db: Session,
    player_name: str,
    match_index: dict[str, list[tuple[Match, str]]],
    knockout_started: bool,
) -> bool:
    """Return true only for a scorer whose route to the award remains live."""
    scorer = resolve_player_by_name(db, player_name, refresh=False)
    if not scorer:
        # Do not claim unsupported future points when a selected player cannot
        # be resolved to a tournament player/team.
        return False

    leaderboard = get_top_scorers(db, refresh=False, limit=50).get("items") or []
    scorer_row = dict(scorer)
    target_key = _canonical_text(player_name)
    for row in leaderboard:
        if scorer.get("player_id") and str(row.get("player_id")) == str(scorer.get("player_id")):
            scorer_row.update(row)
            break
        if _canonical_text(row.get("name")) == target_key:
            scorer_row.update(row)
            break

    team_name = str(scorer_row.get("team") or scorer.get("team") or "").strip()
    if not team_name:
        return False
    if _team_is_still_alive(team_name, match_index, knockout_started):
        return True

    goals = int(scorer_row.get("goals") or 0)
    leader_goals = max((int(row.get("goals") or 0) for row in leaderboard), default=0)
    # A eliminated player remains viable only when they currently share/hold the
    # lead; anything lower can no longer improve and is not a live long-term bet.
    return goals > 0 and goals >= leader_goals


def _tournament_items(
    db: Session,
    prediction: TournamentPrediction | None,
    tournament_resolved: bool,
    match_index: dict[str, list[tuple[Match, str]]],
    knockout_started: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split tournament predictions into still-live and already-dead entries."""
    if not prediction or tournament_resolved:
        return [], []

    live: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for key, points_field, points, label in TOURNAMENT_ITEM_META:
        if int(getattr(prediction, points_field, 0) or 0) > 0:
            continue
        choice = str(getattr(prediction, key, "") or "").strip()
        if not choice:
            continue
        if key == "top_scorer":
            alive = _top_scorer_is_alive(db, choice, match_index, knockout_started)
        else:
            alive = _placement_is_alive(key, choice, match_index, knockout_started)
        item = {
            "key": key,
            "points": points,
            "label": label,
            "choice": choice,
            "text": f"{label}: {choice} (+{points})",
        }
        if alive:
            live.append(item)
        else:
            unavailable.append({**item, "text": f"{label}: {choice} — уже не в игре"})
    return live, unavailable


@dataclass(frozen=True)
class MatchOpportunity:
    stage: str
    is_virtual: bool
    can_score: bool
    can_advancement: bool
    missing_open: bool = False


@dataclass(frozen=True)
class ProbabilitySlot:
    """Model probabilities for one remaining prediction opportunity.

    ``outcome`` includes an exact-score hit; therefore ``exact`` must always
    be less than or equal to it.  The numbers are deliberately estimates, not
    bookmaker odds: they are derived from the Father AI forecast confidence,
    then softened for forecasts that differ from the Father pick.
    """

    exact: float
    outcome: float
    advancement: float
    source: str


def _clamp_probability(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _prediction_outcome(pred_home: int | None, pred_away: int | None) -> str | None:
    if pred_home is None or pred_away is None:
        return None
    if int(pred_home) > int(pred_away):
        return "home"
    if int(pred_away) > int(pred_home):
        return "away"
    return "draw"


def _parse_percent(value: Any) -> float | None:
    """Read percentages stored as 42, 42%, 0.42 or prose text."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric <= 1:
            return _clamp_probability(numeric, 0.0, 1.0)
        return _clamp_probability(numeric / 100.0, 0.0, 1.0)
    found = re.search(r"(\d+(?:[.,]\d+)?)\s*%?", str(value))
    if not found:
        return None
    numeric = float(found.group(1).replace(",", "."))
    return _clamp_probability(numeric / 100.0 if numeric > 1 else numeric, 0.0, 1.0)


def _father_confidence(prediction: FatherMatchPrediction | None) -> float | None:
    if prediction is None:
        return None
    parsed = _parse_percent(getattr(prediction, "confidence", None))
    if parsed is not None:
        return parsed
    text = str(getattr(prediction, "forecast_text", "") or "")
    found = re.search(r"Уверенность\s*:\s*(\d+(?:[.,]\d+)?)%", text, flags=re.IGNORECASE)
    return _parse_percent(found.group(1)) if found else None


@lru_cache(maxsize=1)
def _rankings_store() -> FifaRankingsStore:
    return FifaRankingsStore()


def _rank_strength(home_team: str | None, away_team: str | None) -> float:
    """Return a conservative forecast-confidence fallback from FIFA ranks."""
    try:
        home_row = _rankings_store().get_context(str(home_team or "")) or {}
        away_row = _rankings_store().get_context(str(away_team or "")) or {}
        home_rank = int(home_row.get("rank") or 0)
        away_rank = int(away_row.get("rank") or 0)
    except Exception:
        home_rank = away_rank = 0
    if home_rank <= 0 or away_rank <= 0:
        return 0.50
    spread = abs(home_rank - away_rank) / max(8.0, home_rank + away_rank)
    return _clamp_probability(0.50 + min(0.13, spread * 0.24), 0.48, 0.63)


def _base_probability_slot(match: Match | None, father: FatherMatchPrediction | None) -> ProbabilitySlot:
    """Build probabilities for using the current Father forecast.

    The AI returns a single confidence rather than a full probability
    distribution.  It is converted into conservative probabilities for the
    prediction-game events: exact score, 90-minute outcome and advancement.
    """
    if match is None:
        return ProbabilitySlot(exact=0.11, outcome=0.50, advancement=0.50, source="базовая оценка будущей пары")
    confidence = _father_confidence(father)
    if confidence is None:
        confidence = _rank_strength(match.home_team, match.away_team)
        source = "сила сборных по текущим данным"
    else:
        source = "уверенность текущего ИИ-прогноза Отца"
    # Confidence is not treated as an exact probability.  The conversion is
    # intentionally restrained: even an optimistic football forecast leaves a
    # substantial chance for an upset.
    outcome = _clamp_probability(0.39 + confidence * 0.31, 0.45, 0.70)
    exact = _clamp_probability(0.045 + confidence * 0.14, 0.075, 0.17)
    advancement = _clamp_probability(0.44 + confidence * 0.30, 0.48, 0.74)
    return ProbabilitySlot(exact=min(exact, outcome), outcome=outcome, advancement=advancement, source=source)


def _participant_probability_slot(
    match: Match | None,
    father: FatherMatchPrediction | None,
    prediction: Prediction | None,
) -> ProbabilitySlot:
    """Adjust the Father model for an existing participant prediction.

    If a participant has not made an open forecast yet, the estimate assumes
    they use the Father AI pick.  This makes the assumption explicit in the
    API metadata and prevents treating a missing forecast as guaranteed points.
    """
    base = _base_probability_slot(match, father)
    if match is None or prediction is None:
        return base

    father_outcome = _prediction_outcome(getattr(father, "pred_home", None), getattr(father, "pred_away", None))
    user_outcome = _prediction_outcome(getattr(prediction, "pred_home", None), getattr(prediction, "pred_away", None))
    if father_outcome and user_outcome and user_outcome != father_outcome:
        # The residual probability is split conservatively between the two
        # alternatives.  A counter-pick against a home/away forecast is a bit
        # less likely than its draw alternative.
        residual = max(0.0, 1.0 - base.outcome)
        share = 0.50 if father_outcome == "draw" else (0.43 if user_outcome == "draw" else 0.57)
        outcome = _clamp_probability(residual * share, 0.12, 0.42)
        exact = _clamp_probability(base.exact * 0.22, 0.015, min(0.07, outcome))
    elif father and (prediction.pred_home != father.pred_home or prediction.pred_away != father.pred_away):
        outcome = base.outcome
        exact = _clamp_probability(base.exact * 0.48, 0.035, min(0.11, outcome))
    else:
        outcome = base.outcome
        exact = base.exact

    if bool(getattr(prediction, "advancement_bet_enabled", False)):
        user_side = str(getattr(prediction, "predicted_advancing_side", "") or "")
        father_side = str(getattr(father, "predicted_advancing_side", "") or "") if father else ""
        advancement = base.advancement if user_side and user_side == father_side else _clamp_probability(1.0 - base.advancement, 0.26, 0.52)
    else:
        advancement = 0.0
    return ProbabilitySlot(exact=exact, outcome=max(exact, outcome), advancement=advancement, source=base.source)


def _probability_at_least_score_plan(slots: list[ProbabilitySlot], required_exact: int, required_outcomes: int) -> float:
    """Probability of at least X exact and Y outcome-only hits."""
    required_exact = max(0, int(required_exact or 0))
    required_outcomes = max(0, int(required_outcomes or 0))
    states: dict[tuple[int, int], float] = {(0, 0): 1.0}
    for slot in slots:
        next_states: dict[tuple[int, int], float] = defaultdict(float)
        exact = _clamp_probability(slot.exact, 0.0, 1.0)
        outcome_only = _clamp_probability(slot.outcome - exact, 0.0, 1.0 - exact)
        miss = max(0.0, 1.0 - exact - outcome_only)
        for (exact_count, outcome_count), probability in states.items():
            next_states[(min(required_exact, exact_count + 1), outcome_count)] += probability * exact
            next_states[(exact_count, min(required_outcomes, outcome_count + 1))] += probability * outcome_only
            next_states[(exact_count, outcome_count)] += probability * miss
        states = next_states
    return _clamp_probability(states.get((required_exact, required_outcomes), 0.0), 0.0, 1.0)


def _probability_at_least(values: list[float], required: int) -> float:
    required = max(0, int(required or 0))
    if required == 0:
        return 1.0
    states = [0.0] * (required + 1)
    states[0] = 1.0
    for value in values:
        hit = _clamp_probability(value, 0.0, 1.0)
        next_states = [0.0] * (required + 1)
        for count, probability in enumerate(states):
            next_states[min(required, count + 1)] += probability * hit
            next_states[count] += probability * (1.0 - hit)
        states = next_states
    return _clamp_probability(states[required], 0.0, 1.0)


@lru_cache(maxsize=1)
def _safe_father_tournament_data() -> dict[str, Any]:
    if load_father_tournament_forecast is None:
        return {}
    try:
        return dict(load_father_tournament_forecast() or {})
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _team_strength_probability(team_name: str, match_index: dict[str, list[tuple[Match, str]]]) -> float:
    """Conservative current chance of a live team winning a tournament award."""
    alive = [name for name in match_index if _team_is_still_alive(name, match_index, True)]
    if not alive:
        return 0.06
    try:
        store = _rankings_store()
        weights = []
        selected_weight = None
        for name in alive:
            row = store.get_context(name) or {}
            rank = max(1, int(row.get("rank") or 70))
            weight = 1.0 / math.sqrt(float(rank) + 6.0)
            weights.append(weight)
            if get_team_name_ru(name) == get_team_name_ru(team_name):
                selected_weight = weight
        if selected_weight is None:
            return 0.03
        return _clamp_probability(selected_weight / max(sum(weights), 0.001), 0.02, 0.28)
    except Exception:
        return 0.06


def _tournament_item_probability(
    item: dict[str, Any],
    match_index: dict[str, list[tuple[Match, str]]],
) -> float:
    """Estimate a live tournament-pick chance from Father data or team strength."""
    father_data = _safe_father_tournament_data()
    forecast = father_data.get("forecast") or {}
    confidence = father_data.get("confidence") or {}
    alternatives = father_data.get("alternatives") or {}
    key = str(item.get("key") or "")
    choice = str(item.get("choice") or "")
    if choice and get_team_name_ru(str(forecast.get(key) or "")) == get_team_name_ru(choice):
        parsed = _parse_percent(confidence.get(key))
        if parsed is not None:
            return _clamp_probability(parsed, 0.03, 0.65)
    alternative_choices = [get_team_name_ru(str(value)) for value in (alternatives.get(key) or [])]
    if get_team_name_ru(choice) in alternative_choices:
        baseline = _team_strength_probability(choice, match_index) if key != "top_scorer" else 0.08
        return _clamp_probability(baseline * 1.15, 0.03, 0.22)
    if key == "top_scorer":
        # When player-specific AI data is not present, keep the estimate small
        # and deliberately conservative.  The live/dead check is still done
        # separately by _top_scorer_is_alive.
        return 0.06
    strength = _team_strength_probability(choice, match_index)
    multiplier = {"champion": 1.0, "runner_up": 0.86, "third_place": 0.72}.get(key, 0.70)
    return _clamp_probability(strength * multiplier, 0.02, 0.28)


def _future_extra_points_distribution(
    score_slots: list[ProbabilitySlot],
    advancement_slots: list[ProbabilitySlot],
    tournament_items: list[dict[str, Any]],
    match_index: dict[str, list[tuple[Match, str]]],
) -> dict[int, float]:
    """Return an estimated distribution of future points for one participant.

    It is used only for a rival-limit condition.  The estimates intentionally
    remain separate from actual scoring and are recalculated after every match.
    """
    states: dict[int, float] = {0: 1.0}

    def add_event(values: list[tuple[int, float]]) -> None:
        nonlocal states
        next_states: dict[int, float] = defaultdict(float)
        for current, current_probability in states.items():
            for points, probability in values:
                next_states[current + int(points)] += current_probability * probability
        states = next_states

    for slot in score_slots:
        exact = _clamp_probability(slot.exact, 0.0, 1.0)
        outcome_only = _clamp_probability(slot.outcome - exact, 0.0, 1.0 - exact)
        add_event([(3, exact), (1, outcome_only), (0, max(0.0, 1.0 - exact - outcome_only))])
    for slot in advancement_slots:
        hit = _clamp_probability(slot.advancement, 0.0, 1.0)
        add_event([(1, hit), (0, 1.0 - hit)])
    for item in tournament_items:
        hit = _tournament_item_probability(item, match_index)
        add_event([(int(item.get("points") or 0), hit), (0, 1.0 - hit)])

    return dict(states)


def _probability_at_most_extra(
    score_slots: list[ProbabilitySlot],
    advancement_slots: list[ProbabilitySlot],
    tournament_items: list[dict[str, Any]],
    maximum_points: int,
    match_index: dict[str, list[tuple[Match, str]]],
) -> float:
    distribution = _future_extra_points_distribution(score_slots, advancement_slots, tournament_items, match_index)
    return _clamp_probability(sum(probability for points, probability in distribution.items() if points <= int(maximum_points)), 0.0, 1.0)


def _scenario_probability(
    score_slots: list[ProbabilitySlot],
    advancement_slots: list[ProbabilitySlot],
    plan: dict[str, int],
    tournament_items: list[dict[str, Any]],
    match_index: dict[str, list[tuple[Match, str]]],
    rival_contexts: list[dict[str, Any]] | None = None,
) -> float:
    score_probability = _probability_at_least_score_plan(
        score_slots,
        int(plan.get("exact") or 0),
        int(plan.get("outcomes") or 0),
    )
    advancement_probability = _probability_at_least(
        [slot.advancement for slot in advancement_slots],
        int(plan.get("advancement") or 0),
    )
    longterm_probability = 1.0
    placement_choices = [
        get_team_name_ru(str(item.get("choice") or ""))
        for item in tournament_items
        if item.get("key") in {"champion", "runner_up", "third_place"}
    ]
    if len(placement_choices) != len(set(placement_choices)):
        return 0.0
    for item in tournament_items:
        longterm_probability *= _tournament_item_probability(item, match_index)

    rival_probability = 1.0
    for rival in rival_contexts or []:
        rival_probability *= _probability_at_most_extra(
            score_slots=list(rival.get("score_slots") or []),
            advancement_slots=list(rival.get("advancement_slots") or []),
            tournament_items=list(rival.get("tournament_items") or []),
            maximum_points=int(rival.get("max_extra_allowed") or 0),
            match_index=match_index,
        )
    return _clamp_probability(score_probability * advancement_probability * longterm_probability * rival_probability, 0.0, 1.0)


def _probability_label(probability: float) -> str:
    percent = max(0.0, min(100.0, float(probability) * 100.0))
    if percent < 0.1:
        return "<0,1%"
    return f"{percent:.1f}".replace(".", ",") + "%"


def _bracket_opportunities(
    matches: list[Match],
    predictions_by_user_match: dict[tuple[int, int], Prediction],
    user_id: int,
    now: datetime,
) -> tuple[list[MatchOpportunity], list[dict[str, Any]]]:
    """Construct all remaining 16-match opportunities, including virtual slots."""
    opportunities: list[MatchOpportunity] = []
    breakdown: list[dict[str, Any]] = []

    for stage, expected_count, label in PLAYOFF_PLAN:
        stage_rows = [match for match in matches if _normalized_stage(match) == stage]
        completed = sum(1 for match in stage_rows if bool(match.is_finished))
        remaining_by_schedule = max(0, expected_count - min(expected_count, completed))
        open_rows = [match for match in stage_rows if not bool(match.is_finished)]
        open_rows.sort(key=lambda match: (_utc(match.starts_at) or now, match.id))
        represented = open_rows[:remaining_by_schedule]
        virtual_count = max(0, remaining_by_schedule - len(represented))

        available_score = 0
        available_advancement = 0
        missing_open = 0
        locked_without_prediction = 0
        for match in represented:
            prediction = predictions_by_user_match.get((user_id, match.id))
            starts_at = _utc(match.starts_at) or now
            can_submit = starts_at > now
            has_prediction = prediction is not None
            can_score = has_prediction or can_submit
            can_advancement = can_submit or bool(
                has_prediction and (
                    bool(getattr(prediction, "advancement_bet_enabled", False))
                    or getattr(prediction, "predicted_advancing_side", None) in {"home", "away"}
                )
            )
            if can_score:
                available_score += 1
            elif not has_prediction:
                locked_without_prediction += 1
            if can_advancement:
                available_advancement += 1
            if can_submit and not has_prediction:
                missing_open += 1
            opportunities.append(MatchOpportunity(
                stage=stage,
                is_virtual=False,
                can_score=can_score,
                can_advancement=can_advancement,
                missing_open=can_submit and not has_prediction,
            ))

        # Future bracket slots may not yet be present in the fixtures table,
        # but their teams will be known before prediction lock. They are valid
        # opportunities for every active participant.
        for _ in range(virtual_count):
            opportunities.append(MatchOpportunity(
                stage=stage,
                is_virtual=True,
                can_score=True,
                can_advancement=True,
            ))
        available_score += virtual_count
        available_advancement += virtual_count

        breakdown.append({
            "stage": stage,
            "label": label,
            "scheduled_total": expected_count,
            "completed": completed,
            "remaining": remaining_by_schedule,
            "fixture_rows": len(represented),
            "virtual_future": virtual_count,
            "score_opportunities": available_score,
            "advancement_opportunities": available_advancement,
            "missing_open_predictions": missing_open,
            "locked_without_prediction": locked_without_prediction,
        })

    return opportunities, breakdown


def _probability_slots_for_participant(
    matches: list[Match],
    predictions_by_user_match: dict[tuple[int, int], Prediction],
    father_predictions_by_match: dict[int, FatherMatchPrediction],
    user_id: int,
    now: datetime,
) -> tuple[list[ProbabilitySlot], list[ProbabilitySlot], list[str]]:
    """Return model slots matching exactly the participant's live potential.

    The schedule shape mirrors ``_bracket_opportunities`` so the displayed
    maximum and the probability model never disagree about which matches are
    still available.  For future placeholders the participant is assumed to
    use the Father AI pick when that pair becomes known.
    """
    score_slots: list[ProbabilitySlot] = []
    advancement_slots: list[ProbabilitySlot] = []
    sources: list[str] = []

    for stage, expected_count, _label in PLAYOFF_PLAN:
        stage_rows = [match for match in matches if _normalized_stage(match) == stage]
        completed = sum(1 for match in stage_rows if bool(match.is_finished))
        remaining_by_schedule = max(0, expected_count - min(expected_count, completed))
        open_rows = [match for match in stage_rows if not bool(match.is_finished)]
        open_rows.sort(key=lambda match: (_utc(match.starts_at) or now, match.id))
        represented = open_rows[:remaining_by_schedule]
        virtual_count = max(0, remaining_by_schedule - len(represented))

        for match in represented:
            prediction = predictions_by_user_match.get((user_id, match.id))
            starts_at = _utc(match.starts_at) or now
            can_submit = starts_at > now
            has_prediction = prediction is not None
            can_score = has_prediction or can_submit
            can_advancement = can_submit or bool(
                has_prediction and (
                    bool(getattr(prediction, "advancement_bet_enabled", False))
                    or getattr(prediction, "predicted_advancing_side", None) in {"home", "away"}
                )
            )
            slot = _participant_probability_slot(match, father_predictions_by_match.get(match.id), prediction)
            if can_score:
                score_slots.append(slot)
                sources.append(slot.source)
            if can_advancement:
                advancement_slots.append(slot)

        for _ in range(virtual_count):
            slot = _participant_probability_slot(None, None, None)
            score_slots.append(slot)
            advancement_slots.append(slot)
            sources.append(slot.source)

    return score_slots, advancement_slots, sources


def _participant_potential(
    db: Session,
    user_id: int,
    matches: list[Match],
    predictions_by_user_match: dict[tuple[int, int], Prediction],
    tournament_prediction: TournamentPrediction | None,
    tournament_resolved: bool,
    match_index: dict[str, list[tuple[Match, str]]],
    knockout_started: bool,
    now: datetime,
) -> dict[str, Any]:
    opportunities, breakdown = _bracket_opportunities(matches, predictions_by_user_match, user_id, now)
    score_slots = sum(1 for item in opportunities if item.can_score)
    advancement_slots = sum(1 for item in opportunities if item.can_advancement)
    missing_open = sum(1 for item in opportunities if item.missing_open)
    tournament_items, unavailable_items = _tournament_items(
        db=db,
        prediction=tournament_prediction,
        tournament_resolved=tournament_resolved,
        match_index=match_index,
        knockout_started=knockout_started,
    )
    match_max = 3 * score_slots + advancement_slots
    tournament_max = sum(int(item["points"] or 0) for item in tournament_items)
    return {
        "score_slots": score_slots,
        "advancement_slots": advancement_slots,
        "missing_open": missing_open,
        "match_max": match_max,
        "tournament_items": tournament_items,
        "unavailable_tournament_items": unavailable_items,
        "tournament_max": tournament_max,
        "total_max": match_max + tournament_max,
        "bracket_breakdown": breakdown,
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
                if preference % 3 == 0:
                    complexity = (exact, outcomes, advancement)
                elif preference % 3 == 1:
                    complexity = (-outcomes, exact, advancement)
                else:
                    complexity = (-advancement, exact, outcomes)
                candidates.append(((overshoot, *complexity, exact + outcomes + advancement), {
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



# 6,000 runs provide a stable directional estimate while keeping the periodic
# background refresh inexpensive for medium-sized private leagues. The value can
# be raised for a dedicated deployment without touching application code.
SIMULATION_RUNS = max(2000, int(os.getenv("LEAGUE_WIN_SIMULATION_RUNS", "6000")))
LEAGUE_WIN_CACHE_SCHEMA_VERSION = "v2"



def _build_league_probability_context(db: Session, league: League) -> dict[str, Any]:
    """Build one consistent input set for all chance and scenario calculations."""
    member_rows = _member_rows(db, league)
    users = {user.id: user for _member, user in member_rows}
    table_rows = build_table_rows(db, league_id=league.id)
    rows_by_user = {int(row.get("user_id") or 0): row for row in table_rows}
    now = datetime.now(timezone.utc)
    all_matches = _league_matches(db, league)
    bracket_matches = [match for match in all_matches if _normalized_stage(match) in PLAYOFF_STAGE_COUNTS]
    user_ids = sorted(users)
    match_ids = [match.id for match in bracket_matches]

    predictions: list[Prediction] = []
    if user_ids and match_ids:
        predictions = (
            db.query(Prediction)
            .filter(Prediction.user_id.in_(user_ids), Prediction.match_id.in_(match_ids))
            .all()
        )
    predictions_by_user_match = {(prediction.user_id, prediction.match_id): prediction for prediction in predictions}

    father_predictions_by_match: dict[int, FatherMatchPrediction] = {}
    if match_ids:
        father_predictions_by_match = {
            prediction.match_id: prediction
            for prediction in db.query(FatherMatchPrediction)
            .filter(FatherMatchPrediction.match_id.in_(match_ids))
            .all()
        }

    tournament_predictions = {
        prediction.user_id: prediction
        for prediction in db.query(TournamentPrediction)
        .filter(TournamentPrediction.user_id.in_(user_ids), TournamentPrediction.tournament_code == TOURNAMENT_CODE)
        .all()
    }
    tournament_resolved = db.query(TournamentResult).filter(TournamentResult.tournament_code == TOURNAMENT_CODE).first() is not None
    match_index = _match_index(all_matches)
    knockout_started = any(_normalized_stage(match) not in {"group", ""} for match in all_matches)

    potential_by_user = {
        user_id: _participant_potential(
            db=db,
            user_id=user_id,
            matches=bracket_matches,
            predictions_by_user_match=predictions_by_user_match,
            tournament_prediction=tournament_predictions.get(user_id),
            tournament_resolved=tournament_resolved,
            match_index=match_index,
            knockout_started=knockout_started,
            now=now,
        )
        for user_id in user_ids
    }

    probability_context_by_user: dict[int, dict[str, Any]] = {}
    for user_id in user_ids:
        score_slots, advancement_slots, sources = _probability_slots_for_participant(
            matches=bracket_matches,
            predictions_by_user_match=predictions_by_user_match,
            father_predictions_by_match=father_predictions_by_match,
            user_id=user_id,
            now=now,
        )
        probability_context_by_user[user_id] = {
            "score_slots": score_slots,
            "advancement_slots": advancement_slots,
            "tournament_items": list((potential_by_user.get(user_id) or {}).get("tournament_items") or []),
            "sources": sources,
        }

    current_points_by_user = {
        user_id: int((rows_by_user.get(user_id) or {}).get("points") or 0)
        for user_id in user_ids
    }
    rank_by_user = {
        int(row.get("user_id") or 0): index
        for index, row in enumerate(table_rows, start=1)
        if int(row.get("user_id") or 0)
    }
    return {
        "league": league,
        "users": users,
        "table_rows": table_rows,
        "rows_by_user": rows_by_user,
        "current_points_by_user": current_points_by_user,
        "rank_by_user": rank_by_user,
        "all_matches": all_matches,
        "bracket_matches": bracket_matches,
        "potential_by_user": potential_by_user,
        "probability_context_by_user": probability_context_by_user,
        "match_index": match_index,
    }


def _simulation_seed(context: dict[str, Any]) -> int:
    """Keep displayed chances stable until meaningful prediction data changes."""
    parts: list[str] = [f"league:{context['league'].id}"]
    for user_id in sorted(context["users"]):
        probability_context = context["probability_context_by_user"].get(user_id) or {}
        slot_values = [
            f"{slot.exact:.4f}:{slot.outcome:.4f}:{slot.advancement:.4f}"
            for slot in list(probability_context.get("score_slots") or [])
        ]
        advancement_values = [f"{slot.advancement:.4f}" for slot in list(probability_context.get("advancement_slots") or [])]
        tournament_values = [
            f"{item.get('key')}:{_canonical_text(str(item.get('choice') or ''))}:{int(item.get('points') or 0)}"
            for item in list(probability_context.get("tournament_items") or [])
        ]
        parts.append(
            "|".join(
                [
                    str(user_id),
                    str(context["current_points_by_user"].get(user_id) or 0),
                    ",".join(slot_values),
                    ",".join(advancement_values),
                    ",".join(tournament_values),
                ]
            )
        )
    digest = sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _draw_weighted_choice(rng: Random, weighted: list[tuple[str, float]]) -> str | None:
    if not weighted:
        return None
    total = sum(max(0.0, float(weight)) for _choice, weight in weighted)
    if total <= 0:
        return None
    point = rng.random() * total
    passed = 0.0
    for choice, weight in weighted:
        passed += max(0.0, float(weight))
        if point <= passed:
            return choice
    return weighted[-1][0]


def _draw_longterm_outcomes(
    probability_context_by_user: dict[int, dict[str, Any]],
    match_index: dict[str, list[tuple[Match, str]]],
    rng: Random,
) -> dict[str, str | None]:
    """Sample one shared result for every tournament-prediction category.

    Every participant with the same live pick receives the same result inside a
    simulation.  This avoids the old independent-per-user long-term scoring,
    which could accidentally award the same trophy to incompatible forecasts.
    """
    candidates_by_key: dict[str, dict[str, tuple[str, float]]] = defaultdict(dict)
    for probability_context in probability_context_by_user.values():
        for item in list(probability_context.get("tournament_items") or []):
            key = str(item.get("key") or "")
            choice = str(item.get("choice") or "").strip()
            normalized = _canonical_text(choice)
            if not key or not normalized:
                continue
            probability = _tournament_item_probability(item, match_index)
            previous = candidates_by_key[key].get(normalized)
            if previous is None or probability > previous[1]:
                candidates_by_key[key][normalized] = (choice, probability)

    outcomes: dict[str, str | None] = {}
    used_placement_teams: set[str] = set()
    for key in ("champion", "runner_up", "third_place", "top_scorer"):
        entries = candidates_by_key.get(key) or {}
        weighted: list[tuple[str, float]] = []
        for normalized, (_choice, probability) in entries.items():
            if key in {"champion", "runner_up", "third_place"} and normalized in used_placement_teams:
                continue
            weighted.append((normalized, max(0.0, float(probability))))
        total = sum(weight for _choice, weight in weighted)
        # Leave probability mass for a player/team nobody selected.
        if total > 0.90:
            scale = 0.90 / total
            weighted = [(choice, weight * scale) for choice, weight in weighted]
            total = 0.90
        weighted.append(("__other__", max(0.10, 1.0 - total)))
        outcome = _draw_weighted_choice(rng, weighted)
        outcomes[key] = None if outcome == "__other__" else outcome
        if outcome and key in {"champion", "runner_up", "third_place"}:
            used_placement_teams.add(outcome)
    return outcomes


def _sample_participant_extra(
    probability_context: dict[str, Any],
    longterm_outcomes: dict[str, str | None],
    rng: Random,
) -> dict[str, Any]:
    exact_hits = 0
    outcome_hits = 0
    advancement_hits = 0
    extra_points = 0
    for slot in list(probability_context.get("score_slots") or []):
        exact = _clamp_probability(slot.exact, 0.0, 1.0)
        outcome = _clamp_probability(slot.outcome, exact, 1.0)
        roll = rng.random()
        if roll < exact:
            exact_hits += 1
            extra_points += 3
        elif roll < outcome:
            outcome_hits += 1
            extra_points += 1
    for slot in list(probability_context.get("advancement_slots") or []):
        if rng.random() < _clamp_probability(slot.advancement, 0.0, 1.0):
            advancement_hits += 1
            extra_points += 1

    longterm_keys: list[str] = []
    longterm_points = 0
    for item in list(probability_context.get("tournament_items") or []):
        key = str(item.get("key") or "")
        choice = _canonical_text(str(item.get("choice") or ""))
        if key and choice and longterm_outcomes.get(key) == choice:
            longterm_keys.append(key)
            points = int(item.get("points") or 0)
            longterm_points += points
            extra_points += points
    return {
        "extra_points": extra_points,
        "exact_hits": exact_hits,
        "outcome_hits": outcome_hits,
        "advancement_hits": advancement_hits,
        "longterm_keys": tuple(sorted(longterm_keys)),
        "longterm_points": longterm_points,
    }


def _simulate_league_win_model(context: dict[str, Any], runs: int = SIMULATION_RUNS) -> dict[str, Any]:
    """Monte-Carlo estimate of strict first-place chances for all league members.

    The simulation intentionally models future scoring rather than a single
    ideal path.  It samples the odds derived from the Father forecast/current
    football data and evaluates all participants together in every run.
    """
    user_ids = sorted(context["users"])
    probability_context_by_user = context["probability_context_by_user"]
    current_points_by_user = context["current_points_by_user"]
    rng = Random(_simulation_seed(context))
    winner_counts: dict[int, int] = {user_id: 0 for user_id in user_ids}
    winner_samples: dict[int, list[dict[str, Any]]] = {user_id: [] for user_id in user_ids}

    for _ in range(max(1, int(runs))):
        longterm_outcomes = _draw_longterm_outcomes(
            probability_context_by_user=probability_context_by_user,
            match_index=context["match_index"],
            rng=rng,
        )
        sampled_by_user = {
            user_id: _sample_participant_extra(probability_context_by_user[user_id], longterm_outcomes, rng)
            for user_id in user_ids
        }
        final_points_by_user = {
            user_id: int(current_points_by_user.get(user_id) or 0) + int(sampled_by_user[user_id]["extra_points"] or 0)
            for user_id in user_ids
        }
        highest = max(final_points_by_user.values(), default=0)
        leaders = [user_id for user_id, points in final_points_by_user.items() if points == highest]
        if len(leaders) != 1:
            continue
        winner_id = leaders[0]
        winner_counts[winner_id] += 1
        winner_samples[winner_id].append({
            **sampled_by_user[winner_id],
            "final_points": highest,
            "competitor_extras": {
                user_id: int(sampled_by_user[user_id]["extra_points"] or 0)
                for user_id in user_ids
                if user_id != winner_id
            },
        })

    probabilities = {
        user_id: winner_counts[user_id] / max(1, int(runs))
        for user_id in user_ids
    }
    return {
        "runs": max(1, int(runs)),
        "winner_counts": winner_counts,
        "winner_samples": winner_samples,
        "probabilities": probabilities,
        "unresolved_share": max(0.0, 1.0 - sum(probabilities.values())),
    }


def _bucket_range(value: int, width: int) -> tuple[int, int]:
    value = max(0, int(value or 0))
    low = (value // width) * width
    return low, low + width - 1


def _count_bucket(value: int, thresholds: tuple[int, ...]) -> str:
    value = max(0, int(value or 0))
    for threshold in thresholds:
        if value <= threshold:
            return f"≤{threshold}"
    return f">{thresholds[-1]}"


def _range_text(values: list[int], *, prefix: str = "", suffix: str = "") -> str:
    if not values:
        return f"{prefix}0{suffix}"
    low = min(int(value) for value in values)
    high = max(int(value) for value in values)
    return f"{prefix}{low}{suffix}" if low == high else f"{prefix}{low}–{high}{suffix}"


def _percentile_int(values: list[int], ratio: float = 0.80) -> int:
    if not values:
        return 0
    ordered = sorted(int(value) for value in values)
    index = max(0, min(len(ordered) - 1, math.ceil(float(ratio) * len(ordered)) - 1))
    return ordered[index]


def _build_likely_winning_scenarios(
    *,
    samples: list[dict[str, Any]],
    total_runs: int,
    strict_wins: int,
    target_current_points: int,
    target_potential: dict[str, Any],
    competitors: list[dict[str, Any]],
    target_tournament_items: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Compress winning simulations into readable, high-frequency path classes."""
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        extra_low, _extra_high = _bucket_range(int(sample.get("extra_points") or 0), 4)
        key = (
            extra_low,
            int(sample.get("longterm_points") or 0),
            _count_bucket(int(sample.get("exact_hits") or 0), (0, 1, 2)),
            _count_bucket(int(sample.get("outcome_hits") or 0), (1, 3, 5)),
            _count_bucket(int(sample.get("advancement_hits") or 0), (0, 1, 3)),
        )
        groups[key].append(sample)

    ordered_groups = sorted(
        groups.values(),
        key=lambda group: (-len(group), -sum(int(item.get("final_points") or 0) for item in group) / max(1, len(group))),
    )[:max(1, int(limit or 10))]

    scenarios: list[dict[str, Any]] = []
    for number, group in enumerate(ordered_groups, start=1):
        exact_values = [int(item.get("exact_hits") or 0) for item in group]
        outcome_values = [int(item.get("outcome_hits") or 0) for item in group]
        advancement_values = [int(item.get("advancement_hits") or 0) for item in group]
        extra_values = [int(item.get("extra_points") or 0) for item in group]
        final_values = [int(item.get("final_points") or 0) for item in group]
        plan_text = [f"примерно {_range_text(extra_values, prefix='+')} очк."]
        if max(exact_values) > 0:
            plan_text.append(f"🎯 {_range_text(exact_values)} точных")
        if max(outcome_values) > 0:
            plan_text.append(f"✅ {_range_text(outcome_values)} исходов")
        if max(advancement_values) > 0:
            plan_text.append(f"🟢 {_range_text(advancement_values)} проходов")

        longterm_conditions: list[str] = []
        for item in target_tournament_items:
            key = str(item.get("key") or "")
            hit_count = sum(1 for sample in group if key in set(sample.get("longterm_keys") or ()))
            hit_probability = hit_count / max(1, len(group))
            if hit_probability >= 0.60:
                longterm_conditions.append(f"{item.get('text')} ({_probability_label(hit_probability)})")

        competitor_limits: list[dict[str, Any]] = []
        for competitor in competitors[:3]:
            values = [
                int((sample.get("competitor_extras") or {}).get(int(competitor["user_id"]), 0) or 0)
                for sample in group
            ]
            typical_limit = _percentile_int(values, 0.80)
            competitor_limits.append({
                "user_id": competitor["user_id"],
                "name": competitor["name"],
                "max_extra_allowed": typical_limit,
                "max_extra": competitor["max_extra"],
                "limit_note": "в 80% таких побед",
            })

        overall_probability = len(group) / max(1, int(total_runs))
        conditional_probability = len(group) / max(1, int(strict_wins))
        scenarios.append({
            "number": number,
            "final_points": round(sum(final_values) / max(1, len(final_values))),
            "final_points_range": _range_text(final_values),
            "extra_points": round(sum(extra_values) / max(1, len(extra_values))),
            "extra_points_range": _range_text(extra_values, prefix='+'),
            "plan_text": plan_text,
            "tournament_conditions": longterm_conditions,
            "competitor_limits": competitor_limits,
            "hidden_competitors_count": max(0, len(competitors) - len(competitor_limits)),
            "model_probability": round(overall_probability, 6),
            "model_probability_label": _probability_label(overall_probability),
            "conditional_probability": round(conditional_probability, 6),
            "conditional_probability_label": _probability_label(conditional_probability),
            "samples_count": len(group),
        })
    return scenarios


def _probability_payload_from_simulation(context: dict[str, Any], simulation: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(user_id): {
            "probability": round(float(simulation["probabilities"].get(user_id) or 0.0), 6),
            "label": _probability_label(float(simulation["probabilities"].get(user_id) or 0.0)),
            "simulation_runs": int(simulation["runs"]),
        }
        for user_id in context["users"]
    }


def _build_standings_scenarios_from_context(
    *,
    context: dict[str, Any],
    simulation: dict[str, Any],
    participant_user_id: int,
    limit: int = 10,
) -> dict[str, Any]:
    """Build one participant payload from an already simulated league model."""
    users: dict[int, User] = context["users"]
    if participant_user_id not in users:
        raise ValueError("Участник не состоит в выбранной лиге")

    rows_by_user = context["rows_by_user"]
    target_row = rows_by_user.get(int(participant_user_id))
    if not target_row:
        raise ValueError("Не удалось собрать строку рейтинга участника")

    target_current = int(context["current_points_by_user"].get(participant_user_id) or 0)
    target_potential = context["potential_by_user"][participant_user_id]
    target_max_final = target_current + int(target_potential.get("total_max") or 0)
    competitors: list[dict[str, Any]] = []
    for row in context["table_rows"]:
        user_id = int(row.get("user_id") or 0)
        if not user_id or user_id == participant_user_id or user_id not in users:
            continue
        current = int(row.get("points") or 0)
        potential = context["potential_by_user"].get(user_id) or {}
        competitors.append({
            "user_id": user_id,
            "name": row.get("name") or users[user_id].display_name,
            "current_points": current,
            "max_extra": int(potential.get("total_max") or 0),
            "max_final": current + int(potential.get("total_max") or 0),
        })
    competitors.sort(key=lambda item: (-item["current_points"], item["name"].casefold()))
    leader_current = max((item["current_points"] for item in competitors), default=-1)

    probability_context = context["probability_context_by_user"][participant_user_id]
    strict_wins = int(simulation["winner_counts"].get(participant_user_id) or 0)
    win_probability = float(simulation["probabilities"].get(participant_user_id) or 0.0)
    probability_sources = sorted(set(probability_context.get("sources") or []))

    base_payload = {
        "league": {"id": context["league"].id, "name": context["league"].name},
        "participant": {
            "user_id": participant_user_id,
            "name": users[participant_user_id].display_name,
            "rank": context["rank_by_user"].get(participant_user_id),
            "current_points": target_current,
            "win_probability": round(win_probability, 6),
            "win_probability_label": _probability_label(win_probability),
        },
        "remaining": {
            "matches": sum(int(item["remaining"] or 0) for item in target_potential["bracket_breakdown"]),
            "match_max": int(target_potential["match_max"] or 0),
            "tournament_max": int(target_potential["tournament_max"] or 0),
            "missing_open_predictions": int(target_potential["missing_open"] or 0),
            "max_final_points": target_max_final,
            "bracket_breakdown": target_potential["bracket_breakdown"],
            "live_tournament_items": target_potential["tournament_items"],
            "unavailable_tournament_items": target_potential["unavailable_tournament_items"],
            "score_opportunities": int(target_potential["score_slots"] or 0),
            "advancement_opportunities": int(target_potential["advancement_slots"] or 0),
            "simulation_runs": int(simulation["runs"]),
            "probability_model": {
                "label": "Вероятность — по фоновой симуляции оставшегося турнира",
                "description": (
                    "Модель периодически разыгрывает оставшиеся матчи, проходы и живые долгосрочные ставки "
                    "по текущему ИИ-прогнозу Отца и футбольным данным. Варианты ниже — самые частые "
                    "среди симуляций, где выбранный участник финиширует единоличным первым. "
                    "Данные берутся из фонового кэша: после нового прогноза или результата могут обновиться в течение нескольких минут. "
                    "Это оценка, а не букмекерский коэффициент и не гарантия."
                ),
                "sources": probability_sources,
            },
        },
        "note": (
            "Потолок считается по сетке: 8 матчей 1/8, 4 матча 1/4, 2 полуфинала, "
            "матч за 3-е место и финал. За каждый матч максимум 3 очка за счёт/исход "
            "и 1 за проход; долгосрок включён только для ещё живых ставок."
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

    samples = list(simulation["winner_samples"].get(participant_user_id) or [])
    base_payload["scenarios"] = _build_likely_winning_scenarios(
        samples=samples,
        total_runs=int(simulation["runs"]),
        strict_wins=strict_wins,
        target_current_points=target_current,
        target_potential=target_potential,
        competitors=competitors,
        target_tournament_items=list(probability_context.get("tournament_items") or []),
        limit=limit,
    )
    return base_payload


def build_league_win_model_payload(db: Session, league: League) -> tuple[str, dict[str, Any]]:
    """Calculate the complete reusable payload for one league exactly once."""
    context = _build_league_probability_context(db, league)
    source_signature = f"{LEAGUE_WIN_CACHE_SCHEMA_VERSION}:{_simulation_seed(context):x}"
    simulation = _simulate_league_win_model(context)
    probabilities = _probability_payload_from_simulation(context, simulation)
    scenarios_by_user = {
        str(user_id): _build_standings_scenarios_from_context(
            context=context,
            simulation=simulation,
            participant_user_id=user_id,
            limit=10,
        )
        for user_id in context["users"]
    }
    return source_signature, {
        "schema_version": LEAGUE_WIN_CACHE_SCHEMA_VERSION,
        "league_id": int(league.id),
        "probabilities": {str(user_id): value for user_id, value in probabilities.items()},
        "scenarios_by_user": scenarios_by_user,
        "simulation_runs": int(simulation["runs"]),
        "unresolved_share": round(float(simulation.get("unresolved_share") or 0.0), 6),
    }


def _league_win_cache_row(db: Session, league_id: int) -> LeagueWinModelCache | None:
    return db.query(LeagueWinModelCache).filter(LeagueWinModelCache.league_id == int(league_id)).first()


def get_cached_league_win_model(db: Session, league: League) -> dict[str, Any] | None:
    """Return last successful cache without recalculating in request handlers."""
    row = _league_win_cache_row(db, league.id)
    if not row or row.sync_status != "ready" or not isinstance(row.payload, dict):
        return None
    return dict(row.payload)


def get_cached_league_win_probabilities(db: Session, league: League) -> dict[int, dict[str, Any]] | None:
    payload = get_cached_league_win_model(db, league)
    if not payload:
        return None
    raw = payload.get("probabilities") or {}
    return {int(user_id): dict(value or {}) for user_id, value in raw.items() if str(user_id).isdigit()}


def get_cached_standings_scenarios(
    db: Session,
    league: League,
    participant_user_id: int,
) -> dict[str, Any] | None:
    payload = get_cached_league_win_model(db, league)
    if not payload:
        return None
    cached = (payload.get("scenarios_by_user") or {}).get(str(int(participant_user_id)))
    return dict(cached) if isinstance(cached, dict) else None


def sync_league_win_model_cache(db: Session, league: League, *, force: bool = False) -> dict[str, Any]:
    """Refresh one durable cache row. Intended exclusively for a background job."""
    now = datetime.now(timezone.utc)
    row = _league_win_cache_row(db, league.id)
    if row is None:
        row = LeagueWinModelCache(league_id=league.id, sync_status="pending")
        db.add(row)
        db.flush()

    try:
        # Build the context first: its deterministic signature tells us whether
        # a result/prediction/league change makes the existing cache obsolete.
        context = _build_league_probability_context(db, league)
        signature = f"{LEAGUE_WIN_CACHE_SCHEMA_VERSION}:{_simulation_seed(context):x}"
        if not force and row.sync_status == "ready" and row.source_signature == signature and row.payload:
            row.last_synced_at = now
            db.commit()
            return {"league_id": league.id, "status": "fresh", "recalculated": False}

        simulation = _simulate_league_win_model(context)
        probabilities = _probability_payload_from_simulation(context, simulation)
        scenarios_by_user = {
            str(user_id): _build_standings_scenarios_from_context(
                context=context,
                simulation=simulation,
                participant_user_id=user_id,
                limit=10,
            )
            for user_id in context["users"]
        }
        row.source_signature = signature
        row.payload = {
            "schema_version": LEAGUE_WIN_CACHE_SCHEMA_VERSION,
            "league_id": int(league.id),
            "probabilities": {str(user_id): value for user_id, value in probabilities.items()},
            "scenarios_by_user": scenarios_by_user,
            "simulation_runs": int(simulation["runs"]),
            "unresolved_share": round(float(simulation.get("unresolved_share") or 0.0), 6),
        }
        row.sync_status = "ready"
        row.last_error = None
        row.last_success_at = now
        row.last_synced_at = now
        db.commit()
        return {"league_id": league.id, "status": "ready", "recalculated": True, "runs": int(simulation["runs"])}
    except Exception as error:
        db.rollback()
        row = _league_win_cache_row(db, league.id)
        if row is None:
            row = LeagueWinModelCache(league_id=league.id)
            db.add(row)
        row.sync_status = "partial" if row.payload else "error"
        row.last_synced_at = now
        row.last_error = str(error)[:2000]
        db.commit()
        return {"league_id": league.id, "status": row.sync_status, "recalculated": False, "error": str(error)}


def sync_all_league_win_model_caches(db: Session, *, force: bool = False) -> dict[str, Any]:
    leagues = db.query(League).filter(League.is_active == True).order_by(League.id.asc()).all()
    results = [sync_league_win_model_cache(db, league, force=force) for league in leagues]
    return {
        "leagues": len(results),
        "ready": sum(1 for item in results if item.get("status") in {"ready", "fresh"}),
        "recalculated": sum(1 for item in results if item.get("recalculated")),
        "errors": [item for item in results if item.get("status") == "error"],
    }


def build_league_win_probabilities(db: Session, league: League) -> dict[int, dict[str, Any]]:
    """Compatibility helper for offline/admin callers; web requests use cache."""
    context = _build_league_probability_context(db, league)
    return _probability_payload_from_simulation(context, _simulate_league_win_model(context))


def build_standings_scenarios(
    db: Session,
    league: League,
    participant_user_id: int,
    limit: int = 10,
) -> dict[str, Any]:
    """Compatibility helper for offline/admin callers; web requests use cache."""
    context = _build_league_probability_context(db, league)
    simulation = _simulate_league_win_model(context)
    return _build_standings_scenarios_from_context(
        context=context,
        simulation=simulation,
        participant_user_id=participant_user_id,
        limit=limit,
    )

def _format_bracket_breakdown(remaining: dict[str, Any]) -> str:
    rows = list(remaining.get("bracket_breakdown") or [])
    if not rows:
        return ""
    return "; ".join(
        f"{item.get('label')}: {int(item.get('remaining') or 0)}"
        for item in rows
        if int(item.get("remaining") or 0) > 0
    )


def format_standings_scenarios_telegram(payload: dict[str, Any], max_variants: int = 10) -> str:
    """Render the likeliest strict-first-place paths for a group chat."""
    participant = payload.get("participant") or {}
    remaining = payload.get("remaining") or {}
    name = participant.get("name") or "Участник"
    schedule_text = _format_bracket_breakdown(remaining)
    matches_count = int(remaining.get("matches") or 0)
    fallback_schedule_text = f"{matches_count} {_plural(matches_count, 'матч', 'матча', 'матчей')}"
    lines = [
        f"🏆 Расклады · {name}",
        "",
        f"Сейчас: #{participant.get('rank') or '—'} · {int(participant.get('current_points') or 0)} очк.",
        f"Шанс на единоличное 1-е место: {participant.get('win_probability_label') or '—'}",
        f"Сетка: {schedule_text or fallback_schedule_text}",
        f"Потолок: +{int(remaining.get('match_max') or 0)} за матчи"
        + (f" и +{int(remaining.get('tournament_max') or 0)} за живой долгосрок" if int(remaining.get("tournament_max") or 0) else ""),
    ]
    unavailable = list(remaining.get("unavailable_tournament_items") or [])
    if unavailable:
        lines.append("Не считаются: " + "; ".join(item.get("text") or "" for item in unavailable))

    if not payload.get("is_mathematically_possible"):
        lines.extend(["", "❌ Единоличное 1-е место уже недостижимо.", str(payload.get("elimination_reason") or "")])
        return "\n".join(lines)

    scenarios = list(payload.get("scenarios") or [])[:max_variants]
    if not scenarios:
        lines.extend(["", "В симуляции пока не нашлось победных путей: шанс ниже точности текущей модели."])
        return "\n".join(lines)

    lines.extend(["", "Самые вероятные победные пути:"])
    for scenario in scenarios:
        lines.append("")
        lines.append(
            f"{scenario['number']}. Финиш: {scenario.get('final_points_range') or scenario.get('final_points') or '—'} очк."
        )
        lines.append(
            f"   Доля победных путей: {scenario.get('conditional_probability_label') or '—'} "
            f"· общий шанс: {scenario.get('model_probability_label') or '—'}"
        )
        lines.append("   Обычно: " + " · ".join(scenario.get("plan_text") or []))
        conditions = scenario.get("tournament_conditions") or []
        if conditions:
            lines.append("   Долгосрок: " + "; ".join(conditions))
        limits = scenario.get("competitor_limits") or []
        if limits:
            limits_text = "; ".join(
                f"{item['name']} ≤ +{item['max_extra_allowed']} ({item.get('limit_note') or 'типично'})"
                for item in limits
            )
            lines.append("   Конкуренты: " + limits_text)

    lines.extend([
        "",
        "ℹ️ Проценты — модельная симуляция по ИИ-прогнозу Отца и текущим футбольным данным; это не гарантия. Футбол по-прежнему способен выбрать самый неудобный сценарий.",
    ])
    return "\n".join(lines)[:3900]

