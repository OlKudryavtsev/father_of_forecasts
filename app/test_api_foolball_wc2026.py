import os
import json
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

#API_KEY = os.getenv("API_FOOTBALL_KEY")
API_KEY = "ce231dc3be9d1fc7e11979353081d59a"
BASE_URL = "https://v3.football.api-sports.io"

OUTPUT_DIR = Path("api_football_results")


def api_football_get(endpoint: str, params: dict | None = None) -> dict:
    if not API_KEY:
        raise RuntimeError(
            "API_FOOTBALL_KEY is not set. Add it to .env file."
        )

    headers = {
        "x-apisports-key": API_KEY
    }

    url = f"{BASE_URL}/{endpoint}"

    response = requests.get(
        url,
        headers=headers,
        params=params or {},
        timeout=30
    )

    print(f"GET {response.url}")
    print(f"Status: {response.status_code}")

    response.raise_for_status()

    data = response.json()

    errors = data.get("errors")
    if errors:
        print("API returned errors:")
        print(json.dumps(errors, ensure_ascii=False, indent=2))

    return data


def save_json(filename: str, data: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path = OUTPUT_DIR / filename

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    print(f"Saved: {path}")
    return path


def print_response_summary(name: str, data: dict) -> None:
    print()
    print("=" * 80)
    print(name)
    print("=" * 80)

    print(f"Results: {data.get('results')}")
    print(f"Paging: {data.get('paging')}")
    print(f"Errors: {data.get('errors')}")
    print()


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("API-Football test for World Cup 2026")
    print(f"Output directory: {OUTPUT_DIR.resolve()}")
    print()

    # 1. /countries — проверить ключ
    countries_data = api_football_get("countries")
    print_response_summary("1. Countries / API key check", countries_data)
    save_json(f"{timestamp}_countries.json", countries_data)

    # 2. /leagues?id=1&season=2026 — проверить coverage ЧМ
    league_data = api_football_get(
        "leagues",
        {
            "id": 1,
            "season": 2022,
        }
    )
    print_response_summary("2. World Cup 2026 league coverage", league_data)
    save_json(f"{timestamp}_world_cup_2026_league_coverage.json", league_data)

    # 3. /fixtures?league=1&season=2026 — получить fixture_id матчей
    fixtures_data = api_football_get(
        "fixtures",
        {
            "league": 1,
            "season": 2022,
        }
    )
    print_response_summary("3. World Cup 2026 fixtures", fixtures_data)
    save_json(f"{timestamp}_world_cup_2026_fixtures.json", fixtures_data)

    # Дополнительно сохраним компактный список матчей
    compact_fixtures = []

    for item in fixtures_data.get("response", []):
        fixture = item.get("fixture", {})
        teams = item.get("teams", {})
        venue = fixture.get("venue") or {}
        league = item.get("league", {})

        compact_fixtures.append(
            {
                "fixture_id": fixture.get("id"),
                "date": fixture.get("date"),
                "status": fixture.get("status", {}).get("long"),
                "round": league.get("round"),
                "home_team": teams.get("home", {}).get("name"),
                "home_team_id": teams.get("home", {}).get("id"),
                "away_team": teams.get("away", {}).get("name"),
                "away_team_id": teams.get("away", {}).get("id"),
                "venue_name": venue.get("name"),
                "venue_city": venue.get("city"),
            }
        )

    save_json(
        f"{timestamp}_world_cup_2026_fixtures_compact.json",
        {
            "count": len(compact_fixtures),
            "fixtures": compact_fixtures,
        }
    )

    print()
    print("Done.")
    print(f"Fixtures found: {len(compact_fixtures)}")

    if compact_fixtures:
        print()
        print("First 5 fixtures:")
        for fixture in compact_fixtures[:5]:
            print(
                f"{fixture['fixture_id']} | "
                f"{fixture['date']} | "
                f"{fixture['home_team']} — {fixture['away_team']} | "
                f"{fixture['venue_name']}"
            )


if __name__ == "__main__":
    main()