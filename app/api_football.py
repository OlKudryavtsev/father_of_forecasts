import os
import requests


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

    def get_team_fixtures_between(
        self,
        team_id: int,
        date_from: str,
        date_to: str,
    ) -> list[dict]:
        payload = self.get(
            "/fixtures",
            params={
                "team": team_id,
                "from": date_from,
                "to": date_to,
            },
        )

        return payload.get("response", [])