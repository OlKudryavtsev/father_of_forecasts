from datetime import datetime, timedelta, timezone
from typing import Any

from app.api_football import ApiFootballClient
from app.fifa_rankings import FifaRankingsStore


def normalize_api_fixture_for_history(api_fixture: dict) -> dict:
    fixture = api_fixture["fixture"]
    league = api_fixture.get("league") or {}
    teams = api_fixture.get("teams") or {}
    goals = api_fixture.get("goals") or {}

    return {
        "fixture_id": fixture.get("id"),
        "date": fixture.get("date"),
        "competition": league.get("name"),
        "round": league.get("round"),
        "home_team": (teams.get("home") or {}).get("name"),
        "away_team": (teams.get("away") or {}).get("name"),
        "score_home": goals.get("home"),
        "score_away": goals.get("away"),
        "status": (fixture.get("status") or {}).get("short"),
    }


def is_finished_history_row(row: dict) -> bool:
    return (
        row["status"] in {"FT", "AET", "PEN"}
        and row["score_home"] is not None
        and row["score_away"] is not None
    )


def build_recent_matches_context(
    api_client: ApiFootballClient,
    team_id: int,
    before_date: datetime,
    limit: int = 10,
    lookback_days: int = 730,
) -> list[dict[str, Any]]:
    date_to = (before_date - timedelta(days=1)).date().isoformat()
    date_from = (before_date - timedelta(days=lookback_days)).date().isoformat()

    rows = api_client.get_team_fixtures_between(
        team_id=team_id,
        date_from=date_from,
        date_to=date_to,
    )

    normalized = [
        normalize_api_fixture_for_history(item)
        for item in rows
    ]

    finished = [
        row
        for row in normalized
        if is_finished_history_row(row)
    ]

    finished.sort(key=lambda row: row["date"])

    return finished[-limit:]


def build_h2h_context(
    api_client: ApiFootballClient,
    home_team_id: int | None,
    away_team_id: int | None,
    before_date: datetime,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not home_team_id or not away_team_id:
        return []

    try:
        rows = api_client.get_fixture_head_to_head(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            last=20,
        )
    except Exception as error:
        print(f"Failed to load H2H: {error}")
        return []

    normalized = [
        normalize_api_fixture_for_history(item)
        for item in rows
    ]

    finished = [
        row
        for row in normalized
        if is_finished_history_row(row)
        and row["date"]
        and datetime.fromisoformat(row["date"].replace("Z", "+00:00")) < before_date
    ]

    finished.sort(key=lambda row: row["date"])

    return finished[-limit:]


def calculate_basic_stats(rows: list[dict[str, Any]], team_name: str) -> dict[str, Any]:
    stats = {
        "matches": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
    }

    for row in rows:
        is_home = row["home_team"] == team_name
        is_away = row["away_team"] == team_name

        if not is_home and not is_away:
            continue

        stats["matches"] += 1

        goals_for = row["score_home"] if is_home else row["score_away"]
        goals_against = row["score_away"] if is_home else row["score_home"]

        stats["goals_for"] += goals_for
        stats["goals_against"] += goals_against

        if goals_for > goals_against:
            stats["wins"] += 1
        elif goals_for < goals_against:
            stats["losses"] += 1
        else:
            stats["draws"] += 1

    return stats


def compact_match_rows(rows: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    compact = []

    for row in rows[-limit:]:
        date_text = row["date"][:10] if row.get("date") else None

        compact.append(
            {
                "date": date_text,
                "competition": row.get("competition"),
                "match": f"{row['home_team']} — {row['away_team']}",
                "score": f"{row['score_home']}:{row['score_away']}",
            }
        )

    return compact


def build_wc2026_openai_context(db, match) -> dict[str, Any]:
    api_client = ApiFootballClient()
    rankings = FifaRankingsStore()

    before_date = match.starts_at

    if before_date.tzinfo is None:
        before_date = before_date.replace(tzinfo=timezone.utc)

    home_api_name = match.home_team_api_name or match.home_team
    away_api_name = match.away_team_api_name or match.away_team

    home_ranking = rankings.get_context(home_api_name)
    away_ranking = rankings.get_context(away_api_name)


    home_recent = []
    away_recent = []

    if match.home_external_team_id:
        home_recent = build_recent_matches_context(
            api_client=api_client,
            team_id=match.home_external_team_id,
            before_date=before_date,
        )

    if match.away_external_team_id:
        away_recent = build_recent_matches_context(
            api_client=api_client,
            team_id=match.away_external_team_id,
            before_date=before_date,
        )

    h2h_rows = build_h2h_context(
        api_client=api_client,
        home_team_id=match.home_external_team_id,
        away_team_id=match.away_external_team_id,
        before_date=before_date,
        limit=5,
    )



    return {
        "fixture": {
            "internal_match_id": match.id,
            "external_fixture_id": match.external_fixture_id,
            "date": match.starts_at.isoformat(),
            "stage": match.stage,
            "match_round": match.match_round,
            "group_code": match.group_code,
            "home_team_display": match.home_team,
            "away_team_display": match.away_team,
            "home_team_api_name": home_api_name,
            "away_team_api_name": away_api_name,
        },
        "fifa_rankings_sofascore": {
            home_api_name: home_ranking,
            away_api_name: away_ranking,
        },
        "recent_matches_before_fixture": {
            home_api_name: home_recent,
            away_api_name: away_recent,
        },
        "recent_matches_short": {
            home_api_name: compact_match_rows(home_recent, limit=3),
            away_api_name: compact_match_rows(away_recent, limit=3),
        },
        "recent_form_stats": {
            home_api_name: calculate_basic_stats(home_recent, home_api_name),
            away_api_name: calculate_basic_stats(away_recent, away_api_name),
        },
        "head_to_head": {
            "matches": h2h_rows,
            "matches_short": compact_match_rows(h2h_rows, limit=5),
        },
        "note": (
            "For FIFA ranking, if total_points is null, use rank only. "
            "Lower rank number means stronger team. "
            "Do not treat missing points as missing ranking if rank is available."
        ),
    }