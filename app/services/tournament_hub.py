"""Tournament hub data for Mini App: scorers, player cards and cache warming.

Local match records remain the source of truth for fixtures/results. API-Football
is used only for supplemental player data, and its answers are cached centrally.

The scorer service deliberately merges the provider leaderboard with cached match
events. This keeps team pages useful even when the leaderboard has not yet been
refreshed or a player is outside the provider's returned top-N list.
"""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api_football import ApiFootballClient
from app.models import FantasyPlayer, Match, MatchDetailsCache, TournamentDataCache
from app.runtime import TOURNAMENT_CODE
from app.services.match_details import sync_match_details_cache
from app.services.misc import get_team_flag, get_team_flag_code
from app.team_names import get_team_name_ru

TOP_SCORERS_KEY = "wc2026_top_scorers"
TOP_SCORERS_TTL_SECONDS = max(300, int(os.getenv("TOURNAMENT_SCORERS_TTL_SECONDS", "900")))
FINISHED_DETAILS_WARM_LIMIT = max(1, int(os.getenv("TOURNAMENT_FINISHED_DETAILS_WARM_LIMIT", "4")))
TEAM_DETAILS_WARM_LIMIT = max(1, int(os.getenv("TOURNAMENT_TEAM_DETAILS_WARM_LIMIT", "8")))

# The prediction form stores the Russian display name, while API-Football/Fantasy
# data is commonly English. Keep only well-known spelling/transliteration bridges
# here; all other players are resolved dynamically by exact provider/fantasy names.
PLAYER_NAME_ALIASES = {
    "эрлинг холанд": "erling haaland",
    "холанд": "erling haaland",
    "erling braut haaland": "erling haaland",
    "килиан мбаппе": "kylian mbappe",
    "kylian mbappe": "kylian mbappe",
    "харри кейн": "harry kane",
    "винисиус жуниор": "vinicius junior",
    "vinicius jr": "vinicius junior",
    "лаутаро мартинес": "lautaro martinez",
    "криштиану роналду": "cristiano ronaldo",
    "ромелу лукаку": "romelu lukaku",
    "усман дембеле": "ousmane dembele",
    "лионель месси": "lionel messi",
    "джуд беллингем": "jude bellingham",
    "рафинья": "raphinha",
}

# Used only when a player has not yet appeared in the cached leaderboard/player
# list. It lets the tournament prediction card still show a factual team status.
PLAYER_TEAM_HINTS = {
    "erling haaland": {"team": "Норвегия", "team_api_name": "Norway"},
    "kylian mbappe": {"team": "Франция", "team_api_name": "France"},
    "harry kane": {"team": "Англия", "team_api_name": "England"},
    "vinicius junior": {"team": "Бразилия", "team_api_name": "Brazil"},
    "lautaro martinez": {"team": "Аргентина", "team_api_name": "Argentina"},
    "cristiano ronaldo": {"team": "Португалия", "team_api_name": "Portugal"},
    "romelu lukaku": {"team": "Бельгия", "team_api_name": "Belgium"},
    "ousmane dembele": {"team": "Франция", "team_api_name": "France"},
    "lionel messi": {"team": "Аргентина", "team_api_name": "Argentina"},
    "jude bellingham": {"team": "Англия", "team_api_name": "England"},
    "raphinha": {"team": "Бразилия", "team_api_name": "Brazil"},
}


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _normalize_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-zа-я0-9]+", " ", normalized.casefold()).strip()


def _canonical_player_name(value: str | None) -> str:
    normalized = _normalize_text(value)
    return PLAYER_NAME_ALIASES.get(normalized, normalized)


def _same_player_name(left: str | None, right: str | None) -> bool:
    left_key = _canonical_player_name(left)
    right_key = _canonical_player_name(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    left_parts, right_parts = left_key.split(), right_key.split()
    # Conservative fallback for e.g. "E. Haaland" / "Erling Haaland".
    return (
        len(left_parts) >= 2
        and len(right_parts) >= 2
        and left_parts[-1] == right_parts[-1]
        and left_parts[0][:1] == right_parts[0][:1]
    )


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


def _fantasy_item(player: FantasyPlayer) -> dict[str, Any]:
    return {
        "player_id": player.external_player_id,
        "name": player.player_name,
        "firstname": "",
        "lastname": "",
        "age": player.age,
        "nationality": "",
        "photo": player.photo or "",
        "team_id": player.external_team_id,
        "team": player.team_display_name,
        "team_api_name": player.team_name,
        "team_logo": "",
        "team_flag": get_team_flag(player.team_display_name, player.team_name),
        "team_flag_code": get_team_flag_code(player.team_display_name, player.team_name),
        "goals": 0,
        "assists": 0,
        "appearances": 0,
        "minutes": 0,
        "rating": None,
        "yellow": 0,
        "red": 0,
    }


def _team_matches_id(match: Match, team_id: int | str) -> bool:
    return str(match.home_external_team_id or "") == str(team_id) or str(match.away_external_team_id or "") == str(team_id)


def _event_belongs_to_team(event: dict[str, Any], match: Match, team_id: int | str | None) -> bool:
    if team_id is None:
        return True
    event_team = event.get("team") or {}
    if str(event_team.get("id") or "") == str(team_id):
        return True
    event_name = get_team_name_ru(event_team.get("name") or "")
    if str(match.home_external_team_id or "") == str(team_id) and event_name == get_team_name_ru(match.home_team):
        return True
    if str(match.away_external_team_id or "") == str(team_id) and event_name == get_team_name_ru(match.away_team):
        return True
    return False


def _fallback_scorers_from_match_cache(db: Session, team_id: int | str | None = None) -> list[dict[str, Any]]:
    """Build scorer rows from cached fixture events, optionally for one team."""
    aggregation: dict[int | str, dict[str, Any]] = {}
    query = (
        db.query(Match, MatchDetailsCache)
        .join(MatchDetailsCache, MatchDetailsCache.match_id == Match.id)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
    )
    if team_id is not None:
        query = query.filter(or_(Match.home_external_team_id == int(team_id), Match.away_external_team_id == int(team_id)))
    rows = query.all()

    for match, cache in rows:
        for event in (cache.events_payload or []):
            if str(event.get("type") or "") != "Goal":
                continue
            detail = str(event.get("detail") or "")
            # Own goals affect the score but must not be credited in scorer rankings.
            if "Missed Penalty" in detail or "Own Goal" in detail:
                continue
            if not _event_belongs_to_team(event, match, team_id):
                continue
            player = event.get("player") or {}
            assist = event.get("assist") or {}
            team = event.get("team") or {}

            def ensure_row(person: dict[str, Any]) -> dict[str, Any]:
                person_id = person.get("id") or f"{team.get('id')}-{person.get('name')}"
                return aggregation.setdefault(person_id, {
                    "player_id": person.get("id"),
                    "name": person.get("name") or "Неизвестный игрок",
                    "firstname": "",
                    "lastname": "",
                    "age": None,
                    "nationality": "",
                    "photo": "",
                    "team_id": team.get("id") or team_id,
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

            ensure_row(player)["goals"] += 1
            # API-Football stores the assisting player directly on a goal event.
            # Preserve it in the local fallback so ordering by assists remains
            # correct even before the global leaderboard refreshes.
            if assist.get("id") or assist.get("name"):
                ensure_row(assist)["assists"] += 1
    result = list(aggregation.values())
    result.sort(key=lambda item: (-int(item["goals"] or 0), -int(item["assists"] or 0), item["name"]))
    return result


def _enrich_from_fantasy(db: Session, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add photos/team identifiers to event-only scorer records when available."""
    if not items:
        return items
    fantasy_players = (
        db.query(FantasyPlayer)
        .filter(FantasyPlayer.tournament_code == TOURNAMENT_CODE)
        .order_by(FantasyPlayer.is_active.desc())
        .all()
    )
    for item in items:
        matched = next((player for player in fantasy_players if _same_player_name(player.player_name, item.get("name"))), None)
        if not matched:
            continue
        enriched = _fantasy_item(matched)
        for field in ("player_id", "photo", "team_id", "team", "team_api_name", "team_flag", "team_flag_code"):
            if enriched.get(field) not in (None, "", 0):
                item[field] = enriched[field]
    return items


def _item_key(item: dict[str, Any]) -> str:
    if item.get("player_id") not in (None, ""):
        return f"id:{item['player_id']}"
    return f"name:{_canonical_player_name(item.get('name'))}"


def _cached_player_appearance_counts(db: Session) -> dict[str, int]:
    """Count confirmed tournament appearances from cached fixture player statistics.

    The API-Football leaderboard occasionally lags behind completed fixtures or
    returns zero appearances for a player who is already present in match data.
    Cached per-fixture statistics are therefore used as a factual correction
    layer. A player counts as having appeared only when they recorded minutes
    or another on-pitch statistic, not merely because they were on the bench.
    """
    appearances: dict[str, set[int]] = {}
    rows = (
        db.query(Match, MatchDetailsCache)
        .join(MatchDetailsCache, MatchDetailsCache.match_id == Match.id)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .all()
    )
    for match, cache in rows:
        for team_block in (cache.players_payload or []):
            for item in (team_block.get("players") or []):
                player = item.get("player") or {}
                stat = (item.get("statistics") or [{}])[0] or {}
                games = stat.get("games") or {}
                goals = stat.get("goals") or {}
                cards = stat.get("cards") or {}
                minutes = int(games.get("minutes") or 0)
                involved = any([
                    minutes,
                    int(goals.get("total") or 0),
                    int(goals.get("assists") or 0),
                    int(cards.get("yellow") or 0),
                    int(cards.get("red") or 0),
                ])
                if not involved:
                    continue
                player_id = player.get("id")
                name = player.get("name") or ""
                keys = []
                if player_id not in (None, ""):
                    keys.append(f"id:{player_id}")
                if name:
                    keys.append(f"name:{_canonical_player_name(name)}")
                for key in keys:
                    appearances.setdefault(key, set()).add(int(match.id))
    return {key: len(match_ids) for key, match_ids in appearances.items()}


def _apply_cached_appearance_counts(db: Session, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Raise reported appearance totals to the verified number from match cache."""
    if not items:
        return items
    counts = _cached_player_appearance_counts(db)
    if not counts:
        return items
    for item in items:
        keys = [_item_key(item)]
        if item.get("name"):
            keys.append(f"name:{_canonical_player_name(item.get('name'))}")
        verified = max((int(counts.get(key) or 0) for key in keys), default=0)
        if verified:
            item["appearances"] = max(int(item.get("appearances") or 0), verified)
    return items


def _merge_scorer_rows(*collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge provider and local rows without double-counting tournament totals."""
    merged: dict[str, dict[str, Any]] = {}
    for collection in collections:
        for incoming in collection:
            key = _item_key(incoming)
            current = merged.get(key)
            if current is None:
                merged[key] = dict(incoming)
                continue
            # Local event totals are authoritative for cached matches; use the larger
            # total to avoid adding the same tournament goals twice.
            current["goals"] = max(int(current.get("goals") or 0), int(incoming.get("goals") or 0))
            current["assists"] = max(int(current.get("assists") or 0), int(incoming.get("assists") or 0))
            current["appearances"] = max(int(current.get("appearances") or 0), int(incoming.get("appearances") or 0))
            current["minutes"] = max(int(current.get("minutes") or 0), int(incoming.get("minutes") or 0))
            for field in ("player_id", "photo", "team_id", "team", "team_api_name", "team_logo", "team_flag", "team_flag_code", "firstname", "lastname", "age", "nationality", "rating"):
                if current.get(field) in (None, "", 0) and incoming.get(field) not in (None, "", 0):
                    current[field] = incoming[field]
    rows = list(merged.values())
    rows.sort(key=lambda item: (-int(item.get("goals") or 0), -int(item.get("assists") or 0), item.get("name") or ""))
    return rows


def _hydrate_finished_matches_for_team(db: Session, team_id: int | str, limit: int = TEAM_DETAILS_WARM_LIMIT) -> int:
    """Backfill details once for finished matches of an opened team profile."""
    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.is_finished.is_(True),
            Match.external_fixture_id.isnot(None),
            or_(Match.home_external_team_id == int(team_id), Match.away_external_team_id == int(team_id)),
        )
        .order_by(Match.starts_at.desc())
        .limit(limit)
        .all()
    )
    refreshed = 0
    client: ApiFootballClient | None = None
    for match in matches:
        cache = db.query(MatchDetailsCache).filter(MatchDetailsCache.match_id == match.id).first()
        # A successful empty event list is valid for a 0:0, so do not refetch it.
        if cache and cache.last_success_at:
            continue
        try:
            client = client or ApiFootballClient()
            sync_match_details_cache(db, match, client=client)
            refreshed += 1
        except Exception:
            # Team profile must stay usable with the data it already has.
            continue
    return refreshed


def _hydrate_recent_finished_matches(db: Session, limit: int = FINISHED_DETAILS_WARM_LIMIT) -> int:
    """Gradually populate scorer fallback data after each deployment."""
    matches = (
        db.query(Match)
        .outerjoin(MatchDetailsCache, MatchDetailsCache.match_id == Match.id)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.is_finished.is_(True),
            Match.external_fixture_id.isnot(None),
            MatchDetailsCache.id.is_(None),
        )
        .order_by(Match.starts_at.asc())
        .limit(limit)
        .all()
    )
    if not matches:
        return 0
    try:
        client = ApiFootballClient()
    except Exception:
        return 0
    refreshed = 0
    for match in matches:
        try:
            sync_match_details_cache(db, match, client=client)
            refreshed += 1
        except Exception:
            continue
    return refreshed


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
    api_items = list(((cache.payload or {}).get("items") or []) if cache else [])
    local_items = _enrich_from_fantasy(db, _fallback_scorers_from_match_cache(db))
    items = _merge_scorer_rows(api_items, local_items)
    items = _apply_cached_appearance_counts(db, items)
    items.sort(key=lambda item: (-int(item.get("goals") or 0), -int(item.get("assists") or 0), item.get("name") or ""))
    source = "api-football+match-events" if api_items and local_items else ("api-football" if api_items else "match-events")
    return {
        "items": items[:max(1, min(limit, 50))],
        "source": source,
        "status": getattr(cache, "sync_status", "fallback") if cache else "fallback",
        "last_synced_at": _utc(cache.last_success_at).isoformat() if cache and cache.last_success_at else None,
        "last_error": getattr(cache, "last_error", None) if cache else None,
    }


def get_team_scorers(db: Session, team_id: int | str, *, refresh: bool = True, limit: int = 10) -> list[dict[str, Any]]:
    """Return all known tournament scorers for one national team.

    The first opening of a team may backfill its completed fixture caches; later
    openings are served entirely from PostgreSQL and the shared scorer cache.
    """
    if refresh:
        _hydrate_finished_matches_for_team(db, team_id)
    all_rows = get_top_scorers(db, refresh=refresh, limit=50)["items"]
    local_rows = _enrich_from_fantasy(db, _fallback_scorers_from_match_cache(db, team_id=team_id))
    team_rows = [
        row for row in all_rows
        if str(row.get("team_id") or "") == str(team_id)
    ]
    # Some provider responses omit team_id but retain the team name; include the
    # local event data regardless, then merge by player identity.
    merged = _merge_scorer_rows(team_rows, local_rows)
    return merged[:max(1, min(limit, 50))]


def _team_reference_by_name(db: Session, team_name: str | None) -> dict[str, Any] | None:
    name = get_team_name_ru(team_name)
    if not name:
        return None
    matches = db.query(Match).filter(Match.tournament_code == TOURNAMENT_CODE).order_by(Match.starts_at.asc()).all()
    for match in matches:
        if get_team_name_ru(match.home_team) == name:
            return {"team_id": match.home_external_team_id, "team": name, "team_api_name": match.home_team_api_name or match.home_team}
        if get_team_name_ru(match.away_team) == name:
            return {"team_id": match.away_external_team_id, "team": name, "team_api_name": match.away_team_api_name or match.away_team}
    return None


def resolve_player_by_name(db: Session, player_name: str | None, *, refresh: bool = False) -> dict[str, Any] | None:
    """Resolve a prediction's display name to cached player/team data.

    It handles Russian display names such as «Эрлинг Холанд» and returns a known
    team hint even before the player has scored, so tournament-prediction status
    remains informative.
    """
    if not str(player_name or "").strip():
        return None
    needle = _canonical_player_name(player_name)
    for row in get_top_scorers(db, refresh=refresh, limit=50)["items"]:
        if _same_player_name(row.get("name"), player_name):
            return row

    players = (
        db.query(FantasyPlayer)
        .filter(FantasyPlayer.tournament_code == TOURNAMENT_CODE)
        .order_by(FantasyPlayer.is_active.desc())
        .all()
    )
    for player in players:
        if _same_player_name(player.player_name, player_name):
            return _fantasy_item(player)

    hint = PLAYER_TEAM_HINTS.get(needle)
    if not hint:
        return None
    team_reference = _team_reference_by_name(db, hint.get("team")) or {}
    return {
        "player_id": None,
        "name": str(player_name),
        "photo": "",
        "team_id": team_reference.get("team_id"),
        "team": team_reference.get("team") or hint.get("team"),
        "team_api_name": team_reference.get("team_api_name") or hint.get("team_api_name"),
        "team_flag": get_team_flag(hint.get("team"), hint.get("team_api_name")),
        "team_flag_code": get_team_flag_code(hint.get("team"), hint.get("team_api_name")),
        "goals": 0,
        "assists": 0,
        "appearances": 0,
        "minutes": 0,
    }


def find_top_scorer(db: Session, player_id: int | str) -> dict[str, Any] | None:
    """Find a player card even when the player has not scored yet.

    Top-scorer tables naturally exclude scoreless players, but a user may select
    such a player in the tournament prediction. Fall back to the Fantasy roster
    so their profile link remains valid.
    """
    needle = str(player_id)
    for item in get_top_scorers(db, refresh=True, limit=50)["items"]:
        if str(item.get("player_id")) == needle:
            return item
    try:
        external_id = int(player_id)
    except (TypeError, ValueError):
        return None
    player = (
        db.query(FantasyPlayer)
        .filter(
            FantasyPlayer.tournament_code == TOURNAMENT_CODE,
            FantasyPlayer.external_player_id == external_id,
        )
        .order_by(FantasyPlayer.is_active.desc())
        .first()
    )
    return _fantasy_item(player) if player else None


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
                cards = stat.get("cards") or {}
                if not any([
                    int(games.get("minutes") or 0),
                    int(goals.get("total") or 0),
                    int(goals.get("assists") or 0),
                    int(cards.get("yellow") or 0),
                    int(cards.get("red") or 0),
                ]):
                    continue
                result.append({
                    "match_id": match.id,
                    "home_team": get_team_name_ru(match.home_team),
                    "away_team": get_team_name_ru(match.away_team),
                    "home_flag_code": get_team_flag_code(get_team_name_ru(match.home_team), match.home_team_api_name),
                    "away_flag_code": get_team_flag_code(get_team_name_ru(match.away_team), match.away_team_api_name),
                    "starts_at": _utc(match.starts_at).isoformat(),
                    "score_home": match.score_home,
                    "score_away": match.score_away,
                    "final_score_home": match.final_score_home,
                    "final_score_away": match.final_score_away,
                    "is_finished": bool(match.is_finished),
                    "team": get_team_name_ru(team.get("name") or ""),
                    "minutes": int(games.get("minutes") or 0),
                    "goals": int(goals.get("total") or 0),
                    "assists": int(goals.get("assists") or 0),
                    "rating": games.get("rating"),
                })
    return result


def sync_tournament_hub_cache(db: Session) -> dict[str, Any]:
    """Warm top scorers and gradually backfill finished-match scorer events."""
    result: dict[str, Any] = {}
    try:
        result["finished_match_details"] = _hydrate_recent_finished_matches(db)
    except Exception as error:
        result["finished_match_details"] = "error"
        result["details_error"] = str(error)[:300]
    try:
        cache = sync_top_scorers_cache(db)
        result["top_scorers"] = getattr(cache, "sync_status", "unavailable")
    except Exception as error:
        result["top_scorers"] = "error"
        result["error"] = str(error)
    return result
