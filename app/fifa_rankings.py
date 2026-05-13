import json
from pathlib import Path
from typing import Any


DEFAULT_RANKINGS_PATH = Path(
    "data/sofascore_fifa_rankings_211_2026-05-13_partial_points.json"
)


TEAM_ALIASES = {
    "United States": "USA",
    "USA": "USA",
    "Korea Republic": "South Korea",
    "South Korea": "South Korea",
    "IR Iran": "Iran",
    "Iran": "Iran",
    "Türkiye": "Türkiye",
    "Turkey": "Türkiye",
    "Czech Republic": "Czechia",
    "Ivory Coast": "Côte d'Ivoire",
    "Congo DR": "DR Congo",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
}


def normalize_name(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace(".", "")
        .replace("'", "")
        .replace("&", "and")
    )


class FifaRankingsStore:
    def __init__(self, path: Path = DEFAULT_RANKINGS_PATH):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "rankings": [],
                "by_country": {},
            }

        return json.loads(self.path.read_text(encoding="utf-8"))

    def find(self, team_name: str) -> dict[str, Any] | None:
        canonical_name = TEAM_ALIASES.get(team_name, team_name)

        rankings = self.data.get("rankings", [])

        target = normalize_name(canonical_name)

        for item in rankings:
            country = item.get("country")

            if not country:
                continue

            if normalize_name(country) == target:
                return item

        return None

    def get_context(self, team_name: str) -> dict[str, Any] | None:
        item = self.find(team_name)

        if not item:
            return None

        return {
            "source": "sofascore",
            "rank": item.get("rank"),
            "country": item.get("country"),
            "total_points": item.get("total_points"),
            "previous_points": item.get("previous_points"),
            "change": item.get("change"),
            "points_available": bool(item.get("points_available")),
        }