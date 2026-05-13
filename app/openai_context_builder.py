from collections import defaultdict
from typing import Any

from app.predictor import TeamStats, update_team_stats
from app.team_ratings import get_team_rating


def get_outcome_label(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if away_goals > home_goals:
        return "away"
    return "draw"


def fixture_stage_bucket(round_name: str | None) -> str:
    if not round_name:
        return "unknown"

    value = round_name.lower()

    if "group" in value:
        return "group"

    return "playoff"


def team_stats_to_dict(stats: TeamStats) -> dict[str, Any]:
    return {
        "played": stats.played,
        "wins": stats.wins,
        "draws": stats.draws,
        "losses": stats.losses,
        "goals_for": stats.goals_for,
        "goals_against": stats.goals_against,
        "points": stats.points,
        "points_per_game": round(stats.points_per_game, 2),
        "goal_diff_per_game": round(stats.goal_diff_per_game, 2),
        "goals_for_per_game": round(stats.goals_for_per_game, 2),
        "goals_against_per_game": round(stats.goals_against_per_game, 2),
    }


def get_recent_team_matches(
    already_played_fixtures: list[dict[str, Any]],
    team_name: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    rows = []

    for fixture in reversed(already_played_fixtures):
        if fixture["home_team"] != team_name and fixture["away_team"] != team_name:
            continue

        rows.append(
            {
                "date": fixture["date"],
                "round": fixture.get("round"),
                "home_team": fixture["home_team"],
                "away_team": fixture["away_team"],
                "score": f"{fixture['score_home']}:{fixture['score_away']}",
                "team_was_home": fixture["home_team"] == team_name,
            }
        )

        if len(rows) >= limit:
            break

    return rows


def build_team_stats_from_fixtures(
    already_played_fixtures: list[dict[str, Any]],
) -> dict[str, TeamStats]:
    team_stats = {}

    for fixture in already_played_fixtures:
        update_team_stats(
            team_stats=team_stats,
            home_team=fixture["home_team"],
            away_team=fixture["away_team"],
            score_home=fixture["score_home"],
            score_away=fixture["score_away"],
        )

    return team_stats


def build_openai_prematch_context(
    fixture: dict[str, Any],
    already_played_fixtures: list[dict[str, Any]],
    pre_tournament_context_by_team: dict[str, Any] | None = None,
) -> dict[str, Any]:
    team_stats = build_team_stats_from_fixtures(already_played_fixtures)

    home_team = fixture["home_team"]
    away_team = fixture["away_team"]

    home_stats = team_stats.get(home_team, TeamStats())
    away_stats = team_stats.get(away_team, TeamStats())

    stage = fixture_stage_bucket(fixture.get("round"))

    # Турнирная общая среда на момент матча.
    total_goals = sum(
        played["score_home"] + played["score_away"]
        for played in already_played_fixtures
    )
    played_count = len(already_played_fixtures)

    avg_goals = round(total_goals / played_count, 2) if played_count else None

    pre_tournament_context_by_team = pre_tournament_context_by_team or {}

    home_pre_tournament = pre_tournament_context_by_team.get(home_team)
    away_pre_tournament = pre_tournament_context_by_team.get(away_team)

    return {
        "fixture": {
            "fixture_id": fixture["fixture_id"],
            "date": fixture["date"],
            "round": fixture.get("round"),
            "stage_bucket": stage,
            "home_team": home_team,
            "away_team": away_team,
        },
        "base_ratings": {
            home_team: get_team_rating(home_team),
            away_team: get_team_rating(away_team),
        },
        "tournament_context_before_match": {
            "played_matches_count": played_count,
            "average_goals_per_match": avg_goals,
        },
        "home_team_context": {
            "name": home_team,
            "stats_in_tournament_before_match": team_stats_to_dict(home_stats),
            "recent_matches_before_match": get_recent_team_matches(
                already_played_fixtures,
                home_team,
            ),
        },
        "away_team_context": {
            "name": away_team,
            "stats_in_tournament_before_match": team_stats_to_dict(away_stats),
            "recent_matches_before_match": get_recent_team_matches(
                already_played_fixtures,
                away_team,
            ),
        },
        "pre_tournament_context": {
            home_team: home_pre_tournament,
            away_team: away_pre_tournament,
        },
    }