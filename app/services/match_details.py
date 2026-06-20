"""Cached API-Football match details for the Mini App match screen.

The Mini App never calls API-Football directly.  Every request is served from a
single database cache row per match; the service refreshes stale rows on demand
and the bot runtime warms the cache for live / soon-to-start fixtures.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.api_football import ApiFootballClient
from app.models import Match, MatchDetailsCache


LIVE_TTL_SECONDS = max(30, int(os.getenv("MATCH_DETAILS_LIVE_TTL_SECONDS", "60")))
UPCOMING_TTL_SECONDS = max(300, int(os.getenv("MATCH_DETAILS_UPCOMING_TTL_SECONDS", "900")))
FINISHED_TTL_SECONDS = max(3600, int(os.getenv("MATCH_DETAILS_FINISHED_TTL_SECONDS", "43200")))
IDLE_TTL_SECONDS = max(900, int(os.getenv("MATCH_DETAILS_IDLE_TTL_SECONDS", "21600")))

STAT_LABELS = {
    "Ball Possession": "Владение",
    "Total Shots": "Удары",
    "Shots on Goal": "В створ",
    "Shots off Goal": "Мимо",
    "Blocked Shots": "Блокированные",
    "Corner Kicks": "Угловые",
    "Offsides": "Офсайды",
    "Fouls": "Фолы",
    "Yellow Cards": "Желтые карточки",
    "Red Cards": "Красные карточки",
    "Goalkeeper Saves": "Сейвы",
    "Total passes": "Передачи",
    "Passes accurate": "Точные передачи",
    "Passes %": "Точность передач",
    "expected_goals": "xG",
    "xG": "xG",
}

EVENT_LABELS = {
    "Goal": "Гол",
    "Card": "Карточка",
    "subst": "Замена",
    "Var": "VAR",
}


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _cache_ttl(match: Match, now: datetime) -> int:
    starts_at = _utc(match.starts_at) or now
    if bool(match.is_finished):
        return FINISHED_TTL_SECONDS
    if starts_at <= now:
        return LIVE_TTL_SECONDS
    if starts_at - now <= timedelta(hours=2):
        return UPCOMING_TTL_SECONDS
    return IDLE_TTL_SECONDS


def _cache_is_stale(match: Match, cache: MatchDetailsCache | None, now: datetime, force: bool = False) -> bool:
    if force or not cache or not cache.last_success_at:
        return True
    last_success = _utc(cache.last_success_at)
    if not last_success:
        return True
    return (now - last_success).total_seconds() >= _cache_ttl(match, now)


def _safe_response(callable_):
    try:
        return callable_(), None
    except Exception as error:  # keep previous cache usable on provider trouble
        return None, str(error)


def _event_minute(event: dict[str, Any]) -> str:
    time = event.get("time") or {}
    elapsed = time.get("elapsed")
    extra = time.get("extra")
    if elapsed is None:
        return "—"
    return f"{elapsed}+{extra}'" if extra else f"{elapsed}'"


def _event_type(event: dict[str, Any]) -> str:
    raw = str(event.get("type") or "").strip()
    detail = str(event.get("detail") or "").strip()
    if raw == "Goal":
        if "Own Goal" in detail:
            return "Автогол"
        if "Missed Penalty" in detail:
            return "Незабитый пенальти"
        if "Penalty" in detail:
            return "Пенальти"
    if raw == "Card":
        if "Red" in detail:
            return "Красная карточка"
        if "Yellow" in detail:
            return "Желтая карточка"
    if raw == "subst":
        return "Замена"
    if raw == "Var":
        return "VAR"
    return EVENT_LABELS.get(raw, detail or raw or "Событие")


def _event_icon(event: dict[str, Any]) -> str:
    raw = str(event.get("type") or "")
    detail = str(event.get("detail") or "")
    if raw == "Goal":
        return "⚽"
    if raw == "Card":
        return "🟥" if "Red" in detail else "🟨"
    if raw == "subst":
        return "⇄"
    if raw == "Var":
        return "📺"
    return "•"


def _serialize_event(event: dict[str, Any], home_api_name: str | None, away_api_name: str | None) -> dict[str, Any]:
    team = event.get("team") or {}
    player = event.get("player") or {}
    assist = event.get("assist") or {}
    team_name = team.get("name") or ""
    side = "home" if home_api_name and team_name == home_api_name else "away" if away_api_name and team_name == away_api_name else None
    return {
        "minute": _event_minute(event),
        "minute_sort": int((event.get("time") or {}).get("elapsed") or 0),
        "side": side,
        "team": team_name,
        "type": str(event.get("type") or ""),
        "label": _event_type(event),
        "icon": _event_icon(event),
        "detail": str(event.get("detail") or ""),
        "player": player.get("name") or "",
        "assist": assist.get("name") or "",
        "comments": str(event.get("comments") or ""),
    }


def _serialize_scorers(events: list[dict[str, Any]], home_api_name: str | None, away_api_name: str | None) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in events:
        if str(raw.get("type") or "") != "Goal":
            continue
        detail = str(raw.get("detail") or "")
        if "Missed Penalty" in detail:
            continue
        player = (raw.get("player") or {}).get("name") or "Неизвестный игрок"
        team = (raw.get("team") or {}).get("name") or ""
        side = "home" if home_api_name and team == home_api_name else "away" if away_api_name and team == away_api_name else None
        key = (team, player)
        row = grouped.setdefault(key, {
            "player": player,
            "team": team,
            "side": side,
            "goals": 0,
            "minutes": [],
            "is_own_goal": False,
        })
        row["goals"] += 1
        row["minutes"].append(_event_minute(raw))
        if "Own Goal" in detail:
            row["is_own_goal"] = True

    rows = list(grouped.values())
    rows.sort(key=lambda item: (-item["goals"], item["player"]))
    return rows


def _serialize_statistics(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(payload) < 2:
        return []
    home = payload[0]
    away = payload[1]
    home_stats = {str(item.get("type")): item.get("value") for item in (home.get("statistics") or [])}
    away_stats = {str(item.get("type")): item.get("value") for item in (away.get("statistics") or [])}
    keys = list(dict.fromkeys([*home_stats.keys(), *away_stats.keys()]))
    priority = [
        "Ball Possession", "Total Shots", "Shots on Goal", "Corner Kicks",
        "expected_goals", "xG", "Fouls", "Yellow Cards", "Red Cards",
        "Goalkeeper Saves", "Passes %",
    ]
    keys.sort(key=lambda item: (priority.index(item) if item in priority else len(priority), item))
    rows = []
    for key in keys:
        home_value = home_stats.get(key)
        away_value = away_stats.get(key)
        if home_value is None and away_value is None:
            continue
        rows.append({
            "key": key,
            "label": STAT_LABELS.get(key, key),
            "home": home_value if home_value is not None else "—",
            "away": away_value if away_value is not None else "—",
        })
    return rows


def _serialize_lineups(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for team_block in payload or []:
        team = team_block.get("team") or {}
        start = []
        bench = []
        for entry in team_block.get("startXI") or []:
            player = entry.get("player") or {}
            start.append({
                "name": player.get("name") or "",
                "number": player.get("number"),
                "position": player.get("pos") or "",
            })
        for entry in team_block.get("substitutes") or []:
            player = entry.get("player") or {}
            bench.append({
                "name": player.get("name") or "",
                "number": player.get("number"),
                "position": player.get("pos") or "",
            })
        result.append({
            "team": team.get("name") or "",
            "formation": team_block.get("formation") or "—",
            "coach": (team_block.get("coach") or {}).get("name") or "",
            "start": start,
            "bench": bench,
        })
    return result


def _serialize_player_rows(payload: list[dict[str, Any]], home_api_name: str | None, away_api_name: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for team_block in payload or []:
        team = team_block.get("team") or {}
        team_name = team.get("name") or ""
        side = "home" if home_api_name and team_name == home_api_name else "away" if away_api_name and team_name == away_api_name else None
        for item in team_block.get("players") or []:
            player = item.get("player") or {}
            stat = (item.get("statistics") or [{}])[0] or {}
            games = stat.get("games") or {}
            goals = stat.get("goals") or {}
            shots = stat.get("shots") or {}
            cards = stat.get("cards") or {}
            minutes = games.get("minutes") or 0
            goal_total = goals.get("total") or 0
            assist_total = goals.get("assists") or 0
            if not any([minutes, goal_total, assist_total, shots.get("on") or 0, cards.get("yellow") or 0, cards.get("red") or 0]):
                continue
            rows.append({
                "name": player.get("name") or "",
                "photo": player.get("photo") or "",
                "team": team_name,
                "side": side,
                "position": games.get("position") or "",
                "minutes": minutes,
                "goals": goal_total,
                "assists": assist_total,
                "shots_on": shots.get("on") or 0,
                "yellow": cards.get("yellow") or 0,
                "red": cards.get("red") or 0,
                "rating": games.get("rating"),
            })
    rows.sort(key=lambda item: (-int(item["goals"] or 0), -int(item["assists"] or 0), -float(item["rating"] or 0), item["name"]))
    return rows


def _cache_row(db: Session, match_id: int) -> MatchDetailsCache | None:
    return db.query(MatchDetailsCache).filter(MatchDetailsCache.match_id == match_id).first()


def sync_match_details_cache(
    db: Session,
    match: Match,
    *,
    force: bool = False,
    client: ApiFootballClient | None = None,
) -> MatchDetailsCache | None:
    """Refresh one match cache row if the cached information is stale."""
    if not match.external_fixture_id or (match.external_provider and match.external_provider != "api-football"):
        return _cache_row(db, match.id)

    now = datetime.now(timezone.utc)
    cache = _cache_row(db, match.id)
    if not _cache_is_stale(match, cache, now, force):
        return cache

    if cache is None:
        cache = MatchDetailsCache(match_id=match.id)
        db.add(cache)
        db.flush()

    client = client or ApiFootballClient()
    errors: list[str] = []

    fixture, error = _safe_response(lambda: client.get_fixture_by_id(match.external_fixture_id))
    if error:
        errors.append(f"fixture: {error}")
    elif fixture:
        cache.fixture_payload = fixture

    starts_at = _utc(match.starts_at) or now
    should_load_match_data = bool(match.is_finished or now >= starts_at - timedelta(hours=2))
    if should_load_match_data:
        events, error = _safe_response(lambda: client.get_fixture_events(match.external_fixture_id))
        if error:
            errors.append(f"events: {error}")
        else:
            cache.events_payload = events or []

        statistics, error = _safe_response(lambda: client.get_fixture_statistics(match.external_fixture_id))
        if error:
            errors.append(f"statistics: {error}")
        else:
            cache.statistics_payload = statistics or []

        lineups, error = _safe_response(lambda: client.get_fixture_lineups(match.external_fixture_id))
        if error:
            errors.append(f"lineups: {error}")
        else:
            cache.lineups_payload = lineups or []

        players, error = _safe_response(lambda: client.get_fixture_players(match.external_fixture_id))
        if error:
            errors.append(f"players: {error}")
        else:
            cache.players_payload = players or []

    cache.last_synced_at = now
    if errors:
        cache.last_error = " | ".join(errors)[:2000]
        cache.sync_status = "partial" if cache.fixture_payload else "error"
    else:
        cache.last_error = None
        cache.last_success_at = now
        cache.sync_status = "ready"
    db.commit()
    db.refresh(cache)
    return cache


def build_match_details_payload(db: Session, match: Match, *, refresh: bool = True) -> dict[str, Any]:
    """Return one normalized details payload for PWA tabs, with cache metadata."""
    cache = _cache_row(db, match.id)
    if refresh:
        try:
            cache = sync_match_details_cache(db, match)
        except Exception as error:
            # Return stale cache/local match facts instead of breaking the card.
            cache = _cache_row(db, match.id)
            if cache:
                cache.last_error = str(error)[:2000]
                db.commit()

    fixture = (cache.fixture_payload if cache else None) or {}
    fixture_info = fixture.get("fixture") or {}
    fixture_status = fixture_info.get("status") or {}
    league = fixture.get("league") or {}
    venue = fixture_info.get("venue") or {}
    events_raw = (cache.events_payload if cache else None) or []
    home_api_name = getattr(match, "home_team_api_name", None)
    away_api_name = getattr(match, "away_team_api_name", None)

    events = [_serialize_event(item, home_api_name, away_api_name) for item in events_raw]
    events.sort(key=lambda item: item["minute_sort"])
    scorers = _serialize_scorers(events_raw, home_api_name, away_api_name)
    stats = _serialize_statistics((cache.statistics_payload if cache else None) or [])
    lineups = _serialize_lineups((cache.lineups_payload if cache else None) or [])
    player_rows = _serialize_player_rows((cache.players_payload if cache else None) or [], home_api_name, away_api_name)
    photos_by_player = {row["name"]: row.get("photo") for row in player_rows if row.get("name") and row.get("photo")}
    for scorer in scorers:
        scorer["photo"] = photos_by_player.get(scorer["player"], "")

    is_available = bool(cache and (cache.fixture_payload or cache.events_payload or cache.statistics_payload or cache.lineups_payload or cache.players_payload))
    source_status = getattr(cache, "sync_status", None) if cache else None
    unavailable_reason = None
    if not match.external_fixture_id:
        unavailable_reason = "Для этого матча пока нет внешнего идентификатора API-Football."
    elif not is_available:
        unavailable_reason = "Детали появятся ближе к матчу или после первого обновления данных провайдера."

    fixture_goals = fixture.get("goals") or {}
    live_home_score = fixture_goals.get("home") if fixture_goals.get("home") is not None else match.score_home
    live_away_score = fixture_goals.get("away") if fixture_goals.get("away") is not None else match.score_away

    return {
        "available": is_available,
        "status": source_status or ("pending" if match.external_fixture_id else "unavailable"),
        "last_synced_at": _utc(cache.last_success_at).isoformat() if cache and cache.last_success_at else None,
        "last_error": cache.last_error if cache else None,
        "unavailable_reason": unavailable_reason,
        "overview": {
            "status_short": fixture_status.get("short") or match.status_short,
            "status_long": fixture_status.get("long") or match.status_long,
            "elapsed": fixture_status.get("elapsed"),
            "score_home": live_home_score,
            "score_away": live_away_score,
            "referee": fixture_info.get("referee"),
            "venue": venue.get("name") or match.venue,
            "city": venue.get("city") or match.city,
            "round": league.get("round") or match.api_league_round or match.match_round,
        },
        "events": events,
        "scorers": scorers,
        "statistics": stats,
        "lineups": lineups,
        "players": player_rows,
    }


def sync_active_match_details(
    db: Session,
    *,
    lookback_hours: int = 6,
    lookahead_hours: int = 2,
    limit: int = 8,
) -> dict[str, Any]:
    """Warm cache for live fixtures and matches close enough for official lineups."""
    now = datetime.now(timezone.utc)
    matches = (
        db.query(Match)
        .filter(
            Match.external_provider == "api-football",
            Match.external_fixture_id.isnot(None),
            Match.starts_at >= now - timedelta(hours=max(1, lookback_hours)),
            Match.starts_at <= now + timedelta(hours=max(1, lookahead_hours)),
        )
        .order_by(Match.starts_at.asc())
        .limit(limit)
        .all()
    )

    client = ApiFootballClient()
    refreshed = 0
    errors: list[str] = []
    for match in matches:
        try:
            before = _cache_row(db, match.id)
            before_at = before.last_success_at if before else None
            cache = sync_match_details_cache(db, match, client=client)
            if cache and cache.last_success_at and cache.last_success_at != before_at:
                refreshed += 1
        except Exception as error:
            errors.append(f"{match.home_team} — {match.away_team}: {error}")

    return {"checked": len(matches), "refreshed": refreshed, "errors": errors[:20]}
