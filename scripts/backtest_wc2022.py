from app.api_football import ApiFootballClient
from app.predictor import get_outcome, update_team_stats
from app.predictor_v2 import predict_match_v2
from app.predictor_v3 import predict_match_v3

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
        "score_home": goals["home"],
        "score_away": goals["away"],
        "status": fixture["status"]["short"],
    }


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

    team_stats = {}

    total = 0
    exact = 0
    outcome = 0
    points = 0

    rows = []

    for fixture in fixtures:
        prediction = predict_match_v3(
            home_team=fixture["home_team"],
            away_team=fixture["away_team"],
            team_stats=team_stats,
            stage_or_round=fixture["round"],
        )

        actual_home = fixture["score_home"]
        actual_away = fixture["score_away"]

        total += 1

        if prediction.pred_home == actual_home and prediction.pred_away == actual_away:
            exact += 1
            points += 3
            result_points = 3
        elif get_outcome(prediction.pred_home, prediction.pred_away) == get_outcome(
            actual_home,
            actual_away,
        ):
            outcome += 1
            points += 1
            result_points = 1
        else:
            result_points = 0

        rows.append(
            {
                "match": f"{fixture['home_team']} — {fixture['away_team']}",
                "prediction": f"{prediction.pred_home}:{prediction.pred_away}",
                "actual": f"{actual_home}:{actual_away}",
                "points": result_points,
            }
        )

        update_team_stats(
            team_stats=team_stats,
            home_team=fixture["home_team"],
            away_team=fixture["away_team"],
            score_home=actual_home,
            score_away=actual_away,
        )

    print("Backtest WC-2022")
    print(f"Matches: {total}")
    print(f"Points: {points}")
    print(f"Exact scores: {exact}")
    print(f"Outcomes: {outcome}")

    if total:
        print(f"Points per match: {points / total:.2f}")
        print(f"Exact score rate: {exact / total:.1%}")
        print(f"Outcome rate: {(exact + outcome) / total:.1%}")

    print()
    print("Last 10 predictions:")
    for row in rows[-10:]:
        print(
            f"{row['match']} | прогноз {row['prediction']} | "
            f"факт {row['actual']} | {row['points']} очк."
        )


if __name__ == "__main__":
    main()