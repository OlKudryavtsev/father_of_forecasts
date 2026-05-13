import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.api_football import ApiFootballClient
from app.fifa_rankings_client import FifaRankingsClient
from app.elo_rankings_client import EloRankingsClient

CACHE_DIR = Path("data/pre_tournament_cache")


TEAM_NAME_ALIASES = {
    "USA": "United States",
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
}


def normalize_fixture_for_context(api_fixture: dict) -> dict:
    fixture = api_fixture["fixture"]
    league = api_fixture["league"]
    teams = api_fixture["teams"]
    goals = api_fixture["goals"]

    return {
        "fixture_id": fixture["id"],
        "date": fixture["date"],
        "competition": league.get("name"),
        "round": league.get("round"),
        "home_team": teams["home"]["name"],
        "away_team": teams["away"]["name"],
        "home_team_id": teams["home"]["id"],
        "away_team_id": teams["away"]["id"],
        "score_home": goals["home"],
        "score_away": goals["away"],
        "status": fixture["status"]["short"],
    }


def is_finished_fixture(row: dict) -> bool:
    return (
        row["status"] in {"FT", "AET", "PEN"}
        and row["score_home"] is not None
        and row["score_away"] is not None
    )


def is_world_cup_qualification(row: dict) -> bool:
    competition = (row.get("competition") or "").lower()

    return (
        "world cup" in competition
        and ("qualification" in competition or "qualifiers" in competition)
    )


def get_team_result(row: dict, team_id: int) -> str:
    is_home = row["home_team_id"] == team_id

    team_goals = row["score_home"] if is_home else row["score_away"]
    opponent_goals = row["score_away"] if is_home else row["score_home"]

    if team_goals > opponent_goals:
        return "win"

    if team_goals < opponent_goals:
        return "loss"

    return "draw"


def calculate_qualification_stats(rows: list[dict], team_id: int) -> dict:
    stats = {
        "matches": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
    }

    for row in rows:
        if not is_world_cup_qualification(row):
            continue

        stats["matches"] += 1

        is_home = row["home_team_id"] == team_id

        goals_for = row["score_home"] if is_home else row["score_away"]
        goals_against = row["score_away"] if is_home else row["score_home"]

        stats["goals_for"] += goals_for
        stats["goals_against"] += goals_against

        result = get_team_result(row, team_id)

        if result == "win":
            stats["wins"] += 1
        elif result == "loss":
            stats["losses"] += 1
        else:
            stats["draws"] += 1

    return stats


def format_recent_match(row: dict) -> dict:
    return {
        "date": row["date"],
        "competition": row.get("competition"),
        "round": row.get("round"),
        "match": f"{row['home_team']} — {row['away_team']}",
        "score": f"{row['score_home']}:{row['score_away']}",
    }


def get_cache_path(tournament_code: str, team_id: int) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    return CACHE_DIR / f"{tournament_code}_team_{team_id}.json"


def load_cached_team_context(
    tournament_code: str,
    team_id: int,
) -> dict | None:
    path = get_cache_path(tournament_code, team_id)

    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def save_cached_team_context(
    tournament_code: str,
    team_id: int,
    context: dict,
):
    path = get_cache_path(tournament_code, team_id)

    path.write_text(
        json.dumps(context, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def resolve_fifa_country_name(team_name: str) -> str:
    return TEAM_NAME_ALIASES.get(team_name, team_name)


def build_team_pre_tournament_context(
    api_client: ApiFootballClient,
    fifa_client: FifaRankingsClient | None,
    fifa_rankings: list[dict],
    elo_client: EloRankingsClient | None,
    elo_rankings: list[dict],
    tournament_code: str,
    team_id: int,
    team_name: str,
    tournament_start_date: str,
    lookback_days: int = 730,
    recent_matches_limit: int = 10,
    use_cache: bool = True,
) -> dict:
    if use_cache:
        cached = load_cached_team_context(tournament_code, team_id)
        if cached:
            return cached

    tournament_start = datetime.fromisoformat(
        tournament_start_date.replace("Z", "+00:00")
    )

    date_to = (tournament_start - timedelta(days=1)).date().isoformat()
    date_from = (tournament_start - timedelta(days=lookback_days)).date().isoformat()

    raw_fixtures = api_client.get_team_fixtures_between(
        team_id=team_id,
        date_from=date_from,
        date_to=date_to,
    )

    rows = [
        normalize_fixture_for_context(item)
        for item in raw_fixtures
    ]

    finished_rows = [
        row
        for row in rows
        if is_finished_fixture(row)
    ]

    finished_rows.sort(key=lambda row: row["date"])

    last_matches = [
        format_recent_match(row)
        for row in finished_rows[-recent_matches_limit:]
    ]

    qualification_stats = calculate_qualification_stats(
        rows=finished_rows,
        team_id=team_id,
    )

    fifa_ranking = None
    elo_ranking = None

    if fifa_client:
        fifa_country_name = resolve_fifa_country_name(team_name)
        ranking = fifa_client.find_country_ranking(
            rankings=fifa_rankings,
            country_name=fifa_country_name,
        )

        if ranking:
            fifa_ranking = {
                "country": ranking.get("country")
                or ranking.get("country_name")
                or ranking.get("name")
                or fifa_country_name,
                "rank": ranking.get("rank")
                or ranking.get("ranking")
                or ranking.get("position"),
                "points": ranking.get("points")
                or ranking.get("total_points"),
                "ranking_date": ranking.get("ranking_date")
                or ranking.get("date")
                or tournament_start_date,
            }

    if elo_client:
        elo_country_name = resolve_fifa_country_name(team_name)
        ranking = elo_client.find_country_ranking(
            rankings=elo_rankings,
            country_name=elo_country_name,
        )

        if ranking:
            elo_ranking = {
                "country": ranking.get("country"),
                "rank": ranking.get("rank"),
                "points": ranking.get("points"),
                "source": ranking.get("source", "eloratings.net"),
            }

    context = {
        "team_id": team_id,
        "team_name": team_name,
        "tournament_start_date": tournament_start_date,
        "lookback_period": {
            "from": date_from,
            "to": date_to,
        },
        "fifa_ranking_before_tournament": fifa_ranking,
        "elo_ranking": elo_ranking,
        "last_matches_before_tournament": last_matches,
        "qualification_stats": qualification_stats,
    }

    save_cached_team_context(
        tournament_code=tournament_code,
        team_id=team_id,
        context=context,
    )

    return context


def build_pre_tournament_context_for_fixtures(
    fixtures: list[dict[str, Any]],
    tournament_code: str,
    tournament_start_date: str,
    fifa_ranking_date: str,
) -> dict[str, Any]:
    api_client = ApiFootballClient()

    fifa_client = None
    fifa_rankings = []

    elo_client = None
    elo_rankings = []

    try:
        fifa_client = FifaRankingsClient()
        fifa_rankings = fifa_client.get_rankings_by_date(fifa_ranking_date)
    except Exception as error:
        print(f"FIFA rankings disabled: {error}")

    try:
        elo_client = EloRankingsClient()
        elo_rankings = elo_client.get_latest_rankings()
    except Exception as error:
        print(f"Elo rankings disabled: {error}")

    teams = {}

    for fixture in fixtures:
        teams[fixture["home_team_id"]] = fixture["home_team"]
        teams[fixture["away_team_id"]] = fixture["away_team"]

    context_by_team_name = {}

    for team_id, team_name in teams.items():
        context_by_team_name[team_name] = build_team_pre_tournament_context(
            api_client=api_client,
            fifa_client=fifa_client,
            fifa_rankings=fifa_rankings,
            elo_client=elo_client,
            elo_rankings=elo_rankings,
            tournament_code=tournament_code,
            team_id=team_id,
            team_name=team_name,
            tournament_start_date=tournament_start_date,
        )

    return context_by_team_name