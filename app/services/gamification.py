"""Deterministic gamification, achievements and notification contexts.

All scores, ranks, titles and achievement progress are calculated from the
application database. OpenAI is used only later to phrase the delivered text;
it never decides points, ranks or unlock conditions.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import os

from sqlalchemy.orm import Session

from app.models import League, LeagueMember, Match, Prediction, User, UserAchievement
from app.runtime import TOURNAMENT_CODE
from app.services.leagues import league_scoring_start_at
from app.services.misc import build_table_rows

TOURNAMENT_DAY_TIMEZONE = ZoneInfo(os.getenv("TOURNAMENT_DAY_TIMEZONE", "America/New_York"))

HUMOR_MODES = {
    "ruthless": "Без пощады",
    "ironic": "Футбольная ирония",
    "calm": "Спокойно",
    "numbers": "Только цифры",
}

ACHIEVEMENT_RULES = [
    {
        "code": "precision",
        "title": "Ювелир",
        "description": "Точные счета после запуска сезона достижений",
        "icon": "target",
        "metric": "exact_scores",
        "milestones": [1, 5, 15, 30],
    },
    {
        "code": "outcome_sense",
        "title": "Нюх на исход",
        "description": "Угаданные исходы после запуска сезона достижений",
        "icon": "fire",
        "metric": "outcomes",
        "milestones": [5, 20, 50, 100],
    },
    {
        "code": "hot_streak",
        "title": "На кураже",
        "description": "Серия матчей с очками подряд",
        "icon": "fire",
        "metric": "success_streak",
        "milestones": [3, 5, 8, 12],
    },
    {
        "code": "discipline",
        "title": "Железный график",
        "description": "Сделанные прогнозы на завершённые матчи",
        "icon": "check",
        "metric": "finished_predictions",
        "milestones": [10, 25, 50, 80],
    },
    {
        "code": "perfect_day",
        "title": "Идеальный день",
        "description": "Игровые дни без промахов (минимум два прогноза)",
        "icon": "cup",
        "metric": "perfect_days",
        "milestones": [1, 3, 7],
    },
    {
        "code": "sole_survivor",
        "title": "Последний оракул",
        "description": "Матчи, где очки набрал только ты",
        "icon": "rank",
        "metric": "sole_survivor_hits",
        "milestones": [1, 3, 5],
    },
    {
        "code": "leader",
        "title": "На вершине",
        "description": "Выйти на первое место в лиге",
        "icon": "cup",
        "metric": "leader_now",
        "milestones": [1],
    },
    {
        "code": "no_missed_future",
        "title": "Хладнокровный",
        "description": "Все доступные прогнозы сделаны",
        "icon": "check",
        "metric": "no_missing_future",
        "milestones": [1],
    },
]

LEVEL_NAMES = {0: "В пути", 1: "Бронза", 2: "Серебро", 3: "Золото", 4: "Легенда"}


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _max_time(*values: datetime | None) -> datetime | None:
    normalized = [_ensure_utc(value) for value in values if value is not None]
    return max(normalized) if normalized else None


def normalize_humor_mode(value: str | None, default: str = "ruthless") -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in HUMOR_MODES else default


def _membership(db: Session, user: User, league: League) -> LeagueMember | None:
    return (
        db.query(LeagueMember)
        .filter(
            LeagueMember.league_id == league.id,
            LeagueMember.user_id == user.id,
            LeagueMember.status == "active",
        )
        .first()
    )


def gamification_start_at(league: League, membership: LeagueMember | None = None) -> datetime | None:
    """Return per-user start of the new achievement season.

    Existing tournament statistics remain visible and influence titles, while
    achievements begin from the release migration timestamp so no one instantly
    completes the whole collection on deployment.
    """
    return _max_time(
        league_scoring_start_at(league),
        getattr(league, "gamification_started_at", None),
        getattr(membership, "joined_at", None) if membership else None,
    )


def league_stat_start_at(league: League, membership: LeagueMember | None = None) -> datetime | None:
    """Return normal league scoring window, used for titles/current form."""
    return _max_time(
        league_scoring_start_at(league),
        getattr(membership, "joined_at", None) if membership else None,
    )


def _predictions_in_window(
    db: Session,
    user: User,
    start_at: datetime | None,
    *,
    finished_only: bool = False,
) -> list[Prediction]:
    query = (
        db.query(Prediction)
        .join(Match, Prediction.match_id == Match.id)
        .filter(
            Prediction.user_id == user.id,
            Match.tournament_code == TOURNAMENT_CODE,
        )
    )
    if start_at is not None:
        query = query.filter(Match.starts_at >= start_at)
    if finished_only:
        query = query.filter(
            Match.is_finished == True,
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        )
    return query.order_by(Match.starts_at.asc(), Match.id.asc()).all()


def _future_matches_in_window(db: Session, start_at: datetime | None) -> list[Match]:
    now = datetime.now(timezone.utc)
    query = db.query(Match).filter(
        Match.tournament_code == TOURNAMENT_CODE,
        Match.is_finished == False,
        Match.starts_at > now,
    )
    if start_at is not None:
        query = query.filter(Match.starts_at >= start_at)
    return query.order_by(Match.starts_at.asc(), Match.id.asc()).all()


def _rank_for_user(db: Session, user: User, league: League) -> tuple[int | None, int, list[dict]]:
    rows = build_table_rows(db, league_id=league.id)
    rank = None
    points = 0
    for index, row in enumerate(rows, start=1):
        if int(row.get("user_id") or 0) == int(user.id):
            rank = index
            points = int(row.get("points") or 0)
            break
    return rank, points, rows


def _success_streak(predictions: list[Prediction]) -> int:
    streak = 0
    for prediction in reversed(predictions):
        if int(prediction.points or 0) > 0:
            streak += 1
        else:
            break
    return streak


def _perfect_days(predictions: list[Prediction]) -> int:
    by_day: dict[str, list[Prediction]] = defaultdict(list)
    for prediction in predictions:
        starts_at = _ensure_utc(prediction.match.starts_at)
        if not starts_at:
            continue
        key = starts_at.astimezone(TOURNAMENT_DAY_TIMEZONE).date().isoformat()
        by_day[key].append(prediction)
    return sum(
        1
        for items in by_day.values()
        if len(items) >= 2 and all(int(item.points or 0) > 0 for item in items)
    )


def _sole_survivor_hits(db: Session, user: User, league: League, predictions: list[Prediction]) -> int:
    """Count matches where the user was the only league participant with points."""
    hits = 0
    positive = [item for item in predictions if int(item.points or 0) > 0]
    if not positive:
        return 0

    for prediction in positive:
        match = prediction.match
        peers = (
            db.query(Prediction)
            .join(LeagueMember, LeagueMember.user_id == Prediction.user_id)
            .filter(
                Prediction.match_id == match.id,
                LeagueMember.league_id == league.id,
                LeagueMember.status == "active",
                LeagueMember.joined_at <= match.starts_at,
            )
            .all()
        )
        positive_user_ids = {row.user_id for row in peers if int(row.points or 0) > 0}
        if positive_user_ids == {user.id}:
            hits += 1
    return hits


def _stat_window(
    db: Session,
    user: User,
    league: League,
    *,
    achievements_only: bool,
) -> dict:
    membership = _membership(db, user, league)
    start_at = gamification_start_at(league, membership) if achievements_only else league_stat_start_at(league, membership)
    completed = _predictions_in_window(db, user, start_at, finished_only=True)
    all_predictions = _predictions_in_window(db, user, start_at, finished_only=False)
    predicted_ids = {item.match_id for item in all_predictions}
    future_matches = _future_matches_in_window(db, start_at)
    missing_future = sum(1 for match in future_matches if match.id not in predicted_ids)
    rank, league_points, _rows = _rank_for_user(db, user, league)

    exact_scores = sum(1 for item in completed if int(item.score_points or 0) == 3)
    outcomes = sum(1 for item in completed if int(item.score_points or 0) == 1)
    return {
        "membership": membership,
        "start_at": start_at,
        "finished_predictions": len(completed),
        "total_predictions": len(all_predictions),
        "exact_scores": exact_scores,
        "outcomes": outcomes,
        "success_streak": _success_streak(completed),
        "perfect_days": _perfect_days(completed),
        "sole_survivor_hits": _sole_survivor_hits(db, user, league, completed) if achievements_only else 0,
        "missing_future": missing_future,
        "no_missing_future": 1 if all_predictions and missing_future == 0 else 0,
        "rank": rank,
        "league_points": league_points,
        "leader_now": 1 if rank == 1 else 0,
    }


def calculate_profile_stats(db: Session, user: User, league: League) -> tuple[dict, dict]:
    """Return (normal_stats, achievement_season_stats)."""
    return (
        _stat_window(db, user, league, achievements_only=False),
        _stat_window(db, user, league, achievements_only=True),
    )


def _level(value: int, milestones: list[int]) -> int:
    return sum(1 for milestone in milestones if int(value or 0) >= int(milestone))


def _stored_levels(db: Session, user: User, league: League) -> dict[str, int]:
    rows = (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == user.id, UserAchievement.league_id == league.id)
        .all()
    )
    return {row.achievement_code: int(row.level or 0) for row in rows}


def build_achievement_cards(db: Session, user: User, league: League, stats: dict | None = None) -> list[dict]:
    stats = stats or _stat_window(db, user, league, achievements_only=True)
    stored = _stored_levels(db, user, league)
    cards: list[dict] = []
    for rule in ACHIEVEMENT_RULES:
        value = int(stats.get(rule["metric"]) or 0)
        computed_level = _level(value, rule["milestones"])
        current_level = max(computed_level, int(stored.get(rule["code"], 0) or 0))
        max_level = len(rule["milestones"])
        next_index = min(current_level, max_level - 1)
        goal = int(rule["milestones"][next_index]) if current_level < max_level else int(rule["milestones"][-1])
        progress = min(value, goal) if current_level < max_level else goal
        cards.append({
            "code": rule["code"],
            "title": rule["title"],
            "description": rule["description"],
            "icon": rule["icon"],
            "earned": current_level > 0,
            "level": current_level,
            "level_name": LEVEL_NAMES.get(current_level, "Легенда"),
            "max_level": max_level,
            "progress": int(progress),
            "goal": int(goal),
            "value": value,
            "next_hint": "Максимальный уровень" if current_level >= max_level else f"До следующего уровня: {max(0, goal - value)}",
        })
    return cards


def sync_new_achievements(db: Session, user: User, league: League) -> list[dict]:
    """Persist only newly unlocked achievement levels and return new unlocks."""
    stats = _stat_window(db, user, league, achievements_only=True)
    cards = build_achievement_cards(db, user, league, stats)
    stored_rows = {
        row.achievement_code: row
        for row in db.query(UserAchievement)
        .filter(UserAchievement.user_id == user.id, UserAchievement.league_id == league.id)
        .all()
    }
    unlocked: list[dict] = []
    now = datetime.now(timezone.utc)
    for card in cards:
        new_level = int(card["level"] or 0)
        row = stored_rows.get(card["code"])
        old_level = int(row.level or 0) if row else 0
        if new_level <= old_level:
            continue
        if row is None:
            row = UserAchievement(
                user_id=user.id,
                league_id=league.id,
                achievement_code=card["code"],
                level=new_level,
                earned_at=now,
                updated_at=now,
            )
            db.add(row)
        else:
            row.level = new_level
            row.updated_at = now
            row.earned_at = row.earned_at or now
        unlocked.append({
            "code": card["code"],
            "icon": card["icon"],
            "title": card["title"],
            "level": new_level,
            "level_name": card["level_name"],
            "description": card["description"],
        })
    if unlocked:
        db.commit()
    return unlocked


def build_profile_title(normal_stats: dict) -> dict:
    """Return title + short current form based on deterministic real metrics."""
    exact = int(normal_stats.get("exact_scores") or 0)
    outcomes = int(normal_stats.get("outcomes") or 0)
    finished = int(normal_stats.get("finished_predictions") or 0)
    missing = int(normal_stats.get("missing_future") or 0)
    streak = int(normal_stats.get("success_streak") or 0)
    rank = normal_stats.get("rank")

    if rank == 1:
        title = {"icon": "👑", "label": "Лидер лиги"}
    elif exact >= 5 and (finished == 0 or exact / max(finished, 1) >= 0.14):
        title = {"icon": "🎯", "label": "Хирург счёта"}
    elif outcomes >= 10 and outcomes / max(finished, 1) >= 0.45:
        title = {"icon": "🧠", "label": "Чует исход"}
    elif missing == 0 and finished >= 8:
        title = {"icon": "🧱", "label": "Железная дисциплина"}
    elif streak >= 3:
        title = {"icon": "🔥", "label": "На кураже"}
    elif finished >= 12:
        title = {"icon": "🥷", "label": "Тихий убийца"}
    else:
        title = {"icon": "⚽", "label": "В игре"}

    if streak >= 3:
        form = {"icon": "🔥", "label": f"Очки в {streak} матчах подряд"}
    elif missing > 0:
        form = {"icon": "⏳", "label": f"Ждут прогноза: {missing}"}
    elif rank == 1:
        form = {"icon": "🏆", "label": "Держит первое место"}
    elif finished == 0:
        form = {"icon": "🌱", "label": "Разминается перед первым попаданием"}
    else:
        form = {"icon": "↗️", "label": "Следит за гонкой рейтинга"}
    return {"title": title, "form": form}


def _match_label(match: Match) -> str:
    return f"{match.home_team} — {match.away_team}"


def build_daily_league_context(db: Session, league: League, now: datetime | None = None) -> dict:
    now = _ensure_utc(now) or datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.starts_at >= since,
            Match.starts_at <= now,
            Match.is_finished == True,
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        )
        .order_by(Match.starts_at.asc(), Match.id.asc())
        .all()
    )
    member_rows = (
        db.query(LeagueMember, User)
        .join(User, User.id == LeagueMember.user_id)
        .filter(
            LeagueMember.league_id == league.id,
            LeagueMember.status == "active",
            User.access_status == "approved",
        )
        .all()
    )
    member_names = {user.id: user.display_name for _member, user in member_rows}
    daily: dict[int, dict] = {
        user_id: {"user_id": user_id, "name": name, "points": 0, "exact": 0, "outcomes": 0, "misses": 0, "predictions": 0}
        for user_id, name in member_names.items()
    }
    matches_payload: list[dict] = []
    for match in matches:
        predictions = (
            db.query(Prediction)
            .join(LeagueMember, LeagueMember.user_id == Prediction.user_id)
            .filter(
                Prediction.match_id == match.id,
                LeagueMember.league_id == league.id,
                LeagueMember.status == "active",
                LeagueMember.joined_at <= match.starts_at,
            )
            .all()
        )
        exact = outcomes = misses = 0
        for prediction in predictions:
            row = daily.get(prediction.user_id)
            if row is None:
                continue
            row["predictions"] += 1
            points = int(prediction.points or 0)
            row["points"] += points
            if int(prediction.score_points or 0) == 3:
                exact += 1
                row["exact"] += 1
            elif int(prediction.score_points or 0) == 1:
                outcomes += 1
                row["outcomes"] += 1
            else:
                misses += 1
                row["misses"] += 1
        matches_payload.append({
            "label": _match_label(match),
            "score": f"{match.score_home}:{match.score_away}",
            "exact": exact,
            "outcomes": outcomes,
            "misses": misses,
        })

    daily_rows = sorted(daily.values(), key=lambda row: (-row["points"], -row["exact"], row["name"].casefold()))
    table = build_table_rows(db, league_id=league.id)
    ranks = {int(row.get("user_id") or 0): index for index, row in enumerate(table, start=1)}
    leader = table[0] if table else None
    player_of_day = daily_rows[0] if daily_rows and daily_rows[0]["predictions"] else None
    return {
        "league_name": league.name,
        "period_hours": 24,
        "matches": matches_payload,
        "matches_count": len(matches_payload),
        "daily_rows": daily_rows,
        "leader": {
            "name": leader.get("name"),
            "points": int(leader.get("points") or 0),
        } if leader else None,
        "player_of_day": player_of_day,
        "ranks": ranks,
    }


def build_daily_user_context(db: Session, user: User, league: League, now: datetime | None = None) -> dict:
    league_context = build_daily_league_context(db, league, now)
    row = next((item for item in league_context["daily_rows"] if int(item["user_id"]) == int(user.id)), None)
    rank = league_context["ranks"].get(user.id)
    normal, _season = calculate_profile_stats(db, user, league)
    return {
        "league_name": league.name,
        "user_name": user.display_name,
        "matches_count": league_context["matches_count"],
        "today": row or {"points": 0, "exact": 0, "outcomes": 0, "misses": 0, "predictions": 0},
        "rank": rank,
        "league_points": int(normal.get("league_points") or 0),
        "leader": league_context.get("leader"),
        "player_of_day": league_context.get("player_of_day"),
    }
