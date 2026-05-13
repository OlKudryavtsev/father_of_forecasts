import csv
import json
from pathlib import Path
from typing import Any

from app.api_football import ApiFootballClient
from app.openai_context_builder import build_openai_prematch_context
from app.openai_forecaster import generate_openai_forecast
from app.predictor import get_outcome
from app.pre_tournament_context import build_pre_tournament_context_for_fixtures


CACHE_PATH = Path("data/openai_forecast_cache_wc2022_pretournament_v1.json")
OUTPUT_CSV_PATH = Path("data/openai_backtest_wc2022_pretournament_v1.csv")


def normalize_fixture(api_fixture: dict) -> dict:
    fixture = api_fixture["fixture"]
    teams = api_fixture["teams"]
    goals = api_fixture["goals"]
    league = api_fixture["league"]

    return {
        "fixture_id": fixture["id"],
        "date": fixture["date"],
        "round": league.get("round"),
        "home_team": teams["home"]["name"],
        "away_team": teams["away"]["name"],
        "home_team_id": teams["home"]["id"],
        "away_team_id": teams["away"]["id"],
        "score_home": goals["home"],
        "score_away": goals["away"],
        "status": fixture["status"]["short"],
    }


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}

    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def save_cache(cache: dict[str, Any]):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def calculate_points(
    pred_home: int,
    pred_away: int,
    actual_home: int,
    actual_away: int,
) -> int:
    if pred_home == actual_home and pred_away == actual_away:
        return 3

    if get_outcome(pred_home, pred_away) == get_outcome(actual_home, actual_away):
        return 1

    return 0


def print_stats(rows: list[dict[str, Any]]):
    total = len(rows)
    points = sum(row["points"] for row in rows)
    exact = sum(1 for row in rows if row["points"] == 3)
    outcomes = sum(1 for row in rows if row["points"] == 1)

    print("OpenAI Backtest WC-2022")
    print(f"Matches: {total}")
    print(f"Points: {points}")
    print(f"Exact scores: {exact}")
    print(f"Outcomes: {outcomes}")

    if total:
        print(f"Points per match: {points / total:.2f}")
        print(f"Exact score rate: {exact / total:.1%}")
        print(f"Outcome rate: {(exact + outcomes) / total:.1%}")

    print()
    print("Last 10 predictions:")
    for row in rows[-10:]:
        print(
            f"{row['match']} | прогноз {row['prediction']} | "
            f"факт {row['actual']} | {row['points']} очк. | "
            f"conf {row['confidence']}"
        )


def save_rows_to_csv(rows: list[dict[str, Any]]):
    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "fixture_id",
        "date",
        "round",
        "match",
        "prediction",
        "actual",
        "points",
        "confidence",
        "reason",
    ]

    with OUTPUT_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def main():
    client = ApiFootballClient()

    raw_fixtures = client.get_world_cup_fixtures(season=2022)

    fixtures = [
        normalize_fixture(item)
        for item in raw_fixtures
        if item["fixture"]["status"]["short"] in {"FT", "AET", "PEN"}
        and item["goals"]["home"] is not None
        and item["goals"]["away"] is not None
    ]

    fixtures.sort(key=lambda item: item["date"])

    pre_tournament_context_by_team = build_pre_tournament_context_for_fixtures(
        fixtures=fixtures,
        tournament_code="wc2022",
        tournament_start_date="2022-11-20T00:00:00+00:00",
        fifa_ranking_date="2022-10-06",
    )

    cache = load_cache()
    already_played_fixtures = []

    rows = []

    for fixture in fixtures:
        fixture_id = str(fixture["fixture_id"])

        if fixture_id in cache:
            forecast = cache[fixture_id]
        else:
            context = build_openai_prematch_context(
                fixture=fixture,
                already_played_fixtures=already_played_fixtures,
                pre_tournament_context_by_team=pre_tournament_context_by_team,
            )

            forecast = generate_openai_forecast(context)
            cache[fixture_id] = forecast
            save_cache(cache)

        actual_home = fixture["score_home"]
        actual_away = fixture["score_away"]

        pred_home = int(forecast["pred_home"])
        pred_away = int(forecast["pred_away"])

        points = calculate_points(
            pred_home=pred_home,
            pred_away=pred_away,
            actual_home=actual_home,
            actual_away=actual_away,
        )

        rows.append(
            {
                "fixture_id": fixture["fixture_id"],
                "date": fixture["date"],
                "round": fixture["round"],
                "match": f"{fixture['home_team']} — {fixture['away_team']}",
                "prediction": f"{pred_home}:{pred_away}",
                "actual": f"{actual_home}:{actual_away}",
                "points": points,
                "confidence": forecast.get("confidence"),
                "reason": forecast.get("reason"),
            }
        )

        # Только после прогноза добавляем матч в историю.
        already_played_fixtures.append(fixture)

    save_rows_to_csv(rows)
    print_stats(rows)

    print()
    print(f"CSV saved to: {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()