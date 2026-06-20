import os
import requests
from datetime import date


API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"


class ApiFootballClient:
    def __init__(self):
        self.api_key = os.getenv("API_FOOTBALL_KEY")

        if not self.api_key:
            raise ValueError("API_FOOTBALL_KEY is not set")

        self.headers = {
            "x-apisports-key": self.api_key,
        }

    def get(self, path: str, params: dict | None = None) -> dict:
        response = requests.get(
            f"{API_FOOTBALL_BASE_URL}{path}",
            headers=self.headers,
            params=params or {},
            timeout=30,
        )

        response.raise_for_status()

        payload = response.json()

        if payload.get("errors"):
            raise RuntimeError(f"API-Football errors: {payload['errors']}")

        return payload

    def get_world_cup_fixtures(self, season: int = 2026) -> list[dict]:
        payload = self.get(
            "/fixtures",
            params={
                "league": 1,
                "season": season,
            },
        )

        return payload.get("response", [])

    def get_fixture_by_id(self, fixture_id: int | str) -> dict | None:
        payload = self.get(
            "/fixtures",
            params={
                "id": fixture_id,
            },
        )

        response = payload.get("response", [])

        if not response:
            return None

        return response[0]


    def get_fixture_odds(self, fixture_id: int | str) -> list[dict]:
        """Return bookmaker odds for a fixture, if API-Football has them."""
        payload = self.get(
            "/odds",
            params={
                "fixture": fixture_id,
            },
        )

        return payload.get("response", [])

    def get_fixture_lineups(self, fixture_id: int | str) -> list[dict]:
        """Return official lineups for a fixture, if they are already available."""
        payload = self.get(
            "/fixtures/lineups",
            params={
                "fixture": fixture_id,
            },
        )

        return payload.get("response", [])

    def get_fixture_statistics(self, fixture_id: int | str) -> list[dict]:
        """Return live/post-match fixture statistics, if available."""
        payload = self.get(
            "/fixtures/statistics",
            params={
                "fixture": fixture_id,
            },
        )

        return payload.get("response", [])

    def get_fixture_events(self, fixture_id: int | str) -> list[dict]:
        """Return goals, cards, substitutions and VAR events for one fixture."""
        payload = self.get(
            "/fixtures/events",
            params={
                "fixture": fixture_id,
            },
        )
        return payload.get("response", [])

    def get_fixture_players(self, fixture_id: int | str) -> list[dict]:
        """Return per-player match statistics when API-Football has them."""
        payload = self.get(
            "/fixtures/players",
            params={
                "fixture": fixture_id,
            },
        )
        return payload.get("response", [])

    def get_fixture_head_to_head(
            self,
            home_team_id: int,
            away_team_id: int,
            last: int = 10,
    ) -> list[dict]:
        payload = self.get(
            "/fixtures/headtohead",
            params={
                "h2h": f"{home_team_id}-{away_team_id}",
                "last": last,
            },
        )

        return payload.get("response", [])

    def get_world_cup_top_scorers(self, season: int = 2026) -> list[dict]:
        """Return World Cup player goal leaders for the selected season."""
        payload = self.get(
            "/players/topscorers",
            params={
                "league": 1,
                "season": season,
            },
        )
        return payload.get("response", [])

    def get_player_by_id(self, player_id: int | str, season: int = 2026) -> dict | None:
        """Return a player profile/stat row when provider coverage allows it."""
        payload = self.get(
            "/players",
            params={
                "id": player_id,
                "season": season,
            },
        )
        response = payload.get("response", [])
        return response[0] if response else None

    def get_world_cup_standings(self, season: int = 2026) -> list[dict]:
        payload = self.get(
            "/standings",
            params={
                "league": 1,
                "season": season,
            },
        )

        response = payload.get("response", [])

        if not response:
            return []

        league = response[0].get("league", {})
        return league.get("standings", [])

    def get_team_fixtures_between(
            self,
            team_id: int,
            date_from: str,
            date_to: str,
            seasons: list[int] | None = None,
    ) -> list[dict]:
        """
        API-Football требует season при запросе fixtures по team.
        Поэтому для периода в несколько лет делаем несколько запросов:
        season=2024, season=2025, season=2026 и т.д.
        """

        if seasons is None:
            start_year = date.fromisoformat(date_from).year
            end_year = date.fromisoformat(date_to).year
            seasons = list(range(start_year, end_year + 1))

        fixtures_by_id = {}

        for season in seasons:
            payload = self.get(
                "/fixtures",
                params={
                    "team": team_id,
                    "season": season,
                    "from": date_from,
                    "to": date_to,
                },
            )

            for item in payload.get("response", []):
                fixture_id = item.get("fixture", {}).get("id")

                if fixture_id:
                    fixtures_by_id[fixture_id] = item

        fixtures = list(fixtures_by_id.values())

        fixtures.sort(
            key=lambda item: item.get("fixture", {}).get("date") or ""
        )

        return fixtures