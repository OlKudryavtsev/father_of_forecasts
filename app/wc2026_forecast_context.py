from datetime import datetime, timedelta, timezone
import os
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



def summarize_odds_for_forecast(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a compact optional odds context for OpenAI.

    The function intentionally returns only a small market snapshot, because raw
    bookmaker responses can be very large and noisy for an LLM prompt.
    """
    if not rows:
        return {
            "available": False,
            "reason": "API-Football returned no odds for this fixture.",
        }

    bookmakers_count = 0
    markets: dict[str, dict[str, Any]] = {}

    for row in rows:
        for bookmaker in row.get("bookmakers") or []:
            bookmakers_count += 1

            for bet in bookmaker.get("bets") or []:
                market_name = bet.get("name")

                if not market_name:
                    continue

                market = markets.setdefault(
                    market_name,
                    {
                        "values": {},
                        "samples": 0,
                    },
                )

                for value in bet.get("values") or []:
                    label = value.get("value")
                    odd = value.get("odd")

                    if label is None or odd is None:
                        continue

                    try:
                        odd_float = float(odd)
                    except (TypeError, ValueError):
                        continue

                    bucket = market["values"].setdefault(
                        str(label),
                        {
                            "odds": [],
                        },
                    )
                    bucket["odds"].append(odd_float)
                    market["samples"] += 1

    compact_markets = {}

    for market_name, market in markets.items():
        compact_values = {}

        for label, bucket in market["values"].items():
            odds = bucket["odds"]

            if not odds:
                continue

            avg_odds = sum(odds) / len(odds)

            compact_values[label] = {
                "avg_odds": round(avg_odds, 3),
                "implied_probability": round(1 / avg_odds, 3) if avg_odds > 0 else None,
                "bookmakers": len(odds),
            }

        if compact_values:
            compact_markets[market_name] = {
                "samples": market["samples"],
                "values": compact_values,
            }

    preferred_market_names = [
        "Match Winner",
        "Home/Away",
        "Goals Over/Under",
        "Both Teams Score",
        "Double Chance",
    ]

    selected_markets = {
        name: compact_markets[name]
        for name in preferred_market_names
        if name in compact_markets
    }

    if not selected_markets:
        for name in sorted(compact_markets.keys())[:5]:
            selected_markets[name] = compact_markets[name]

    return {
        "available": bool(selected_markets),
        "bookmakers_count": bookmakers_count,
        "markets": selected_markets,
        "note": (
            "Odds are optional market context. Implied probabilities are not "
            "margin-adjusted and should be interpreted carefully."
        ),
    }


def summarize_lineups_for_forecast(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a compact optional lineups context for OpenAI."""
    if not rows:
        return {
            "available": False,
            "reason": "API-Football returned no official lineups for this fixture.",
        }

    teams = []

    for row in rows:
        team = row.get("team") or {}
        coach = row.get("coach") or {}

        starters = []
        substitutes = []

        for item in row.get("startXI") or []:
            player = item.get("player") or {}
            name = player.get("name")

            if name:
                starters.append(name)

        for item in row.get("substitutes") or []:
            player = item.get("player") or {}
            name = player.get("name")

            if name:
                substitutes.append(name)

        teams.append(
            {
                "team": team.get("name"),
                "formation": row.get("formation"),
                "coach": coach.get("name"),
                "starters": starters,
                "substitutes": substitutes[:12],
            }
        )

    return {
        "available": True,
        "teams": teams,
        "note": "Official lineups should strongly influence the forecast if available.",
    }


def build_optional_external_forecast_context(
    api_client: ApiFootballClient,
    match,
) -> dict[str, Any]:
    """Fetch optional API-Football forecast inputs.

    This is intentionally a soft/fallback context. If odds or lineups are absent
    or API-Football temporarily fails, forecast generation must continue using
    rankings, recent form and H2H data.
    """
    enabled = os.getenv("FORECAST_EXTERNAL_CONTEXT_ENABLED", "true").lower() == "true"

    context = {
        "enabled": enabled,
        "odds": {
            "available": False,
            "reason": "external context disabled",
        },
        "lineups": {
            "available": False,
            "reason": "external context disabled",
        },
        "data_quality": {
            "odds_available": False,
            "lineups_available": False,
            "notes": [],
        },
    }

    fixture_id = getattr(match, "external_fixture_id", None)

    if not enabled:
        context["data_quality"]["notes"].append(
            "External odds/lineups context is disabled by FORECAST_EXTERNAL_CONTEXT_ENABLED."
        )
        return context

    if not fixture_id:
        context["odds"]["reason"] = "match has no external_fixture_id"
        context["lineups"]["reason"] = "match has no external_fixture_id"
        context["data_quality"]["notes"].append(
            "No external_fixture_id is stored for this match."
        )
        return context

    try:
        odds_rows = api_client.get_fixture_odds(fixture_id)
        context["odds"] = summarize_odds_for_forecast(odds_rows)
    except Exception as error:
        context["odds"] = {
            "available": False,
            "reason": f"failed to fetch odds: {error}",
        }

    try:
        lineups_rows = api_client.get_fixture_lineups(fixture_id)
        context["lineups"] = summarize_lineups_for_forecast(lineups_rows)
    except Exception as error:
        context["lineups"] = {
            "available": False,
            "reason": f"failed to fetch lineups: {error}",
        }

    context["data_quality"] = {
        "odds_available": bool(context["odds"].get("available")),
        "lineups_available": bool(context["lineups"].get("available")),
        "notes": [
            "Use odds and lineups only if available=true.",
            "If odds or lineups are unavailable, do not invent bookmaker lines, squads, injuries or absences.",
            "Do not mention unavailable external blocks in the user-facing forecast unless they materially affect confidence.",
        ],
    }

    return context


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

    external_context = build_optional_external_forecast_context(
        api_client=api_client,
        match=match,
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
        "external_context": external_context,
        "note": (
            "For FIFA ranking, if total_points is null, use rank only. "
            "Lower rank number means stronger team. "
            "Do not treat missing points as missing ranking if rank is available."
        ),
    }