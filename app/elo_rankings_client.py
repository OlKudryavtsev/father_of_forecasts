import re
from datetime import datetime
from typing import Any

import requests


ELORATINGS_BASE_URL = "https://www.eloratings.net"


TEAM_ALIASES = {
    "USA": "United States",
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "Türkiye": "Turkey",
}


def normalize_team_name(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace(".", "")
        .replace("'", "")
    )


def resolve_elo_team_name(team_name: str) -> str:
    return TEAM_ALIASES.get(team_name, team_name)


class EloRankingsClient:
    def get_rankings_for_date(self, ranking_date: str) -> list[dict[str, Any]]:
        """
        eloratings.net умеет отдавать рейтинги по году:
        https://www.eloratings.net/2022

        Для backtest WC-2022 это будет рейтинг на конец 2022 года,
        не идеально до турнира. Поэтому для строгого backtest лучше использовать
        /latest только для текущих прогнозов, а для 2022 — отдельный historical source.
        Но как автоматический fallback это уже лучше, чем ничего.
        """

        year = datetime.fromisoformat(ranking_date).year

        response = requests.get(
            f"{ELORATINGS_BASE_URL}/{year}",
            timeout=20,
        )

        response.raise_for_status()

        return parse_elo_rankings_text(response.text)

    def get_latest_rankings(self) -> list[dict[str, Any]]:
        response = requests.get(
            f"{ELORATINGS_BASE_URL}/latest",
            timeout=20,
        )

        response.raise_for_status()

        return parse_elo_rankings_text(response.text)

    def find_country_ranking(
        self,
        rankings: list[dict[str, Any]],
        country_name: str,
    ) -> dict[str, Any] | None:
        target = normalize_team_name(resolve_elo_team_name(country_name))

        for item in rankings:
            if normalize_team_name(item["country"]) == target:
                return item

        return None


def parse_elo_rankings_text(text: str) -> list[dict[str, Any]]:
    rankings = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        # Примеры строк могут быть разными, поэтому парсим мягко:
        # "1. Spain 2165"
        # "1 Spain 2165"
        match = re.match(
            r"^\s*(\d+)\.?\s+(.+?)\s+(\d{3,4})\s*$",
            line,
        )

        if not match:
            continue

        rank = int(match.group(1))
        country = match.group(2).strip()
        points = int(match.group(3))

        rankings.append(
            {
                "country": country,
                "rank": rank,
                "points": points,
                "source": "eloratings.net",
            }
        )

    return rankings