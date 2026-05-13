import os
import requests


FOOTBALLDATA_IO_BASE_URL = "https://footballdata.io/api/v1"


class FifaRankingsClient:
    def __init__(self):
        self.api_key = os.getenv("FOOTBALLDATA_IO_KEY")

        if not self.api_key:
            raise ValueError("FOOTBALLDATA_IO_KEY is not set")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

    def get_rankings_by_date(self, ranking_date: str) -> list[dict]:
        response = requests.get(
            f"{FOOTBALLDATA_IO_BASE_URL}/fifa-rankings",
            headers=self.headers,
            params={
                "ranking_type": "men",
                "date": ranking_date,
                "limit": 300,
            },
            timeout=20,
        )

        response.raise_for_status()

        payload = response.json()

        if isinstance(payload, dict):
            return payload.get("data", payload.get("rankings", []))

        return payload

    def find_country_ranking(
        self,
        rankings: list[dict],
        country_name: str,
    ) -> dict | None:
        target = normalize_country_name(country_name)

        for item in rankings:
            possible_names = [
                item.get("country"),
                item.get("country_name"),
                item.get("team"),
                item.get("name"),
            ]

            for name in possible_names:
                if name and normalize_country_name(name) == target:
                    return item

        return None


def normalize_country_name(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace(".", "")
    )