"""Tournament hub data for Mini App: scorers, player cards and cache warming.

Local match records remain the source of truth for fixtures/results.  API-Football
is used only for supplemental player data, and its answers are cached centrally.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.api_football import ApiFootballClient
from app.models import Match, MatchDetailsCache, TournamentDataCache
from app.runtime import TOURNAMENT_CODE
from app.services.misc import get_team_flag, get_team_flag_code
from app.team_names import get_team_name_ru

TOP_SCORERS_KEY = "wc2026_top_scorers"
TOP_SCORERS_TTL_SECONDS = max(300, int(os.getenv("TOURNAMENT_SCORERS_TTL_SECONDS", "900")))


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _cache_row(db: Session, key: str) -> TournamentDataCache | None:
    return db.query(TournamentDataCache).filter(TournamentDataCache.cache_key == key).first()


def _is_stale(cache: TournamentDataCache | None, ttl_seconds: int, now: datetime, force: bool = False) -> bool:
    if force or not cache:
        return True
    # A failed provider request should not be retried by every Mini App opening.
    # Keep stale cached data usable and retry only after the normal cache interval.
    last_attempt = _utc(cache.last_success_at or cache.last_synced_at)
    return not last_attempt or (now - last_attempt).total_seconds() >= ttl_seconds


def _normalize_top_scorer(raw: dict[str, Any]) -> dict[str, Any]:
    player = raw.get("player") or {}
    statistics = (raw.get("statistics") or [{}])[0] or {}
    team = statistics.get("team") or {}
    goals = statistics.get("goals") or {}
    games = statistics.get("games") or {}
    cards = statistics.get("cards") or {}
    return {
        "player_id": player.get("id"),
        "name": player.get("name") or "Неизвестный игрок",
        "firstname": player.get("firstname") or "",
        "lastname": player.get("lastname") or "",
        "age": player.get("age"),
        "nationality": player.get("nationality") or "",
        "photo": player.get("photo") or "",
        "team_id": team.get("id"),
        "team": get_team_name_ru(team.get("name") or ""),
        "team_api_name": team.get("name") or "",
        "team_logo": team.get("logo") or "",
        "team_flag": get_team_flag(get_team_name_ru(team.get("name") or ""), team.get("name")),
        "team_flag_code": get_team_flag_code(get_team_name_ru(team.get("name") or ""), team.get("name")),
        "goals": int(goals.get("total") or 0),
        "assists": int(goals.get("assists") or 0),
        "appearances": int(games.get("appearences") or games.get("appearances") or 0),
        "minutes": int(games.get("minutes") or 0),
        "rating": games.get("rating"),
        "yellow": int(cards.get("yellow") or 0),
        "red": int(cards.get("red") or 0),
    }


def _fallback_scorers_from_match_cache(db: Session) -> list[dict[str, Any]]:
    """Build a useful scorer table when provider leaderboard is temporarily unavailable."""
    aggregation: dict[int | str, dict[str, Any]] = {}
    rows = (
        db.query(Match, MatchDetailsCache)
        .join(MatchDetailsCache, MatchDetailsCache.match_id == Match.id)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .all()
    )
    for match, cache in rows:
        for event in (cache.events_payload or []):
            if str(event.get("type") or "") != "Goal":
                continue
            if "Missed Penalty" in str(event.get("detail") or ""):
                continue
            player = event.get("player") or {}
            team = event.get("team") or {}
            player_id = player.get("id") or f"{team.get('id')}-{player.get('name')}"
            row = aggregation.setdefault(player_id, {
                "player_id": player.get("id"),
                "name": player.get("name") or "Неизвестный игрок",
                "firstname": "",
                "lastname": "",
                "age": None,
                "nationality": "",
                "photo": "",
                "team_id": team.get("id"),
                "team": get_team_name_ru(team.get("name") or ""),
                "team_api_name": team.get("name") or "",
                "team_logo": "",
                "team_flag": get_team_flag(get_team_name_ru(team.get("name") or ""), team.get("name")),
                "team_flag_code": get_team_flag_code(get_team_name_ru(team.get("name") or ""), team.get("name")),
                "goals": 0,
                "assists": 0,
                "appearances": 0,
                "minutes": 0,
                "rating": None,
                "yellow": 0,
                "red": 0,
            })
            row["goals"] += 1
    result = list(aggregation.values())
    result.sort(key=lambda item: (-item["goals"], -item["assists"], item["name"]))
    return result


def sync_top_scorers_cache(
    db: Session,
    *,
    force: bool = False,
    client: ApiFootballClient | None = None,
) -> TournamentDataCache | None:
    now = datetime.now(timezone.utc)
    cache = _cache_row(db, TOP_SCORERS_KEY)
    if not _is_stale(cache, TOP_SCORERS_TTL_SECONDS, now, force):
        return cache

    if cache is None:
        cache = TournamentDataCache(cache_key=TOP_SCORERS_KEY)
        db.add(cache)
        db.flush()

    try:
        client = client or ApiFootballClient()
        raw_rows = client.get_world_cup_top_scorers(season=2026)
        cache.payload = {"items": [_normalize_top_scorer(item) for item in raw_rows]}
        cache.sync_status = "ready"
        cache.last_error = None
        cache.last_success_at = now
    except Exception as error:
        cache.last_error = str(error)[:2000]
        cache.sync_status = "partial" if cache.payload else "error"
    cache.last_synced_at = now
    db.commit()
    db.refresh(cache)
    return cache


def get_top_scorers(db: Session, *, refresh: bool = True, limit: int = 10) -> dict[str, Any]:
    cache = _cache_row(db, TOP_SCORERS_KEY)
    if refresh:
        try:
            cache = sync_top_scorers_cache(db)
        except Exception:
            cache = _cache_row(db, TOP_SCORERS_KEY)
    items = list(((cache.payload or {}).get("items") or []) if cache else [])
    source = "api-football"
    if not items:
        items = _fallback_scorers_from_match_cache(db)
        source = "match-events"
    items.sort(key=lambda item: (-int(item.get("goals") or 0), -int(item.get("assists") or 0), item.get("name") or ""))
    return {
        "items": items[:max(1, min(limit, 50))],
        "source": source,
        "status": getattr(cache, "sync_status", "fallback") if cache else "fallback",
        "last_synced_at": _utc(cache.last_success_at).isoformat() if cache and cache.last_success_at else None,
        "last_error": getattr(cache, "last_error", None) if cache else None,
    }


def find_top_scorer(db: Session, player_id: int | str) -> dict[str, Any] | None:
    needle = str(player_id)
    for item in get_top_scorers(db, refresh=True, limit=50)["items"]:
        if str(item.get("player_id")) == needle:
            return item
    return None


def player_match_rows(db: Session, player_id: int | str) -> list[dict[str, Any]]:
    """Return cached per-match player appearances, without provider calls."""
    needle = str(player_id)
    result: list[dict[str, Any]] = []
    rows = (
        db.query(Match, MatchDetailsCache)
        .join(MatchDetailsCache, MatchDetailsCache.match_id == Match.id)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.desc())
        .all()
    )
    for match, cache in rows:
        for team_block in (cache.players_payload or []):
            team = team_block.get("team") or {}
            for item in (team_block.get("players") or []):
                player = item.get("player") or {}
                if str(player.get("id")) != needle:
                    continue
                stat = (item.get("statistics") or [{}])[0] or {}
                games = stat.get("games") or {}
                goals = stat.get("goals") or {}
                result.append({
                    "match_id": match.id,
                    "home_team": get_team_name_ru(match.home_team),
                    "away_team": get_team_name_ru(match.away_team),
                    "home_flag_code": get_team_flag_code(get_team_name_ru(match.home_team), match.home_team_api_name),
                    "away_flag_code": get_team_flag_code(get_team_name_ru(match.away_team), match.away_team_api_name),
                    "starts_at": _utc(match.starts_at).isoformat(),
                    "score_home": match.score_home,
                    "score_away": match.score_away,
                    "is_finished": bool(match.is_finished),
                    "team": get_team_name_ru(team.get("name") or ""),
                    "minutes": int(games.get("minutes") or 0),
                    "goals": int(goals.get("total") or 0),
                    "assists": int(goals.get("assists") or 0),
                    "rating": games.get("rating"),
                })
    return result


def sync_tournament_hub_cache(db: Session) -> dict[str, Any]:
    """Warm the tournament-wide data which benefits most from caching."""
    try:
        cache = sync_top_scorers_cache(db)
        return {"top_scorers": getattr(cache, "sync_status", "unavailable")}
    except Exception as error:
        return {"top_scorers": "error", "error": str(error)}
