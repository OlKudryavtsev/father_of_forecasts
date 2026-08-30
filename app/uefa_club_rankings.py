"""Official UEFA club coefficient snapshot used for UCL forecasts.

The snapshot is intentionally fixed at the end of the 2025/26 season.  UEFA
uses that reference point in its 2026/27 Champions League league-phase team
profiles, so forecasts made during the new season do not accidentally use
future results from later matchdays.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.team_identity import get_team_identity, normalize_team_name


DEFAULT_RANKINGS_PATH = Path("data/uefa_club_rankings_2026_2027.json")
UCL_TOURNAMENT_CODE = "ucl_2026_2027"


class UefaClubRankingsStore:
    def __init__(self, path: Path = DEFAULT_RANKINGS_PATH):
        self.path = path
        self.data = self._load()
        self._index = self._build_index()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            print(f"UEFA club rankings file not found: {self.path}")
            return {"rankings": []}

        data = json.loads(self.path.read_text(encoding="utf-8"))
        rankings_count = len(data.get("rankings", []))
        print(f"Loaded UEFA club rankings: {rankings_count} rows from {self.path}")
        return data

    def _build_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for item in self.data.get("rankings", []):
            for value in (item.get("club"), item.get("name_ru")):
                key = normalize_team_name(value)
                if key:
                    index[key] = item
        return index

    def find(self, team_name: str | None) -> dict[str, Any] | None:
        raw_name = str(team_name or "").strip()
        if not raw_name:
            return None

        direct = self._index.get(normalize_team_name(raw_name))
        if direct:
            return direct

        # Reuse the application's canonical club aliases (VfB Stuttgart ->
        # Штутгарт, Viking FK -> Викинг, Sabah FA -> Сабах, etc.) instead of
        # maintaining a second alias catalogue inside the rankings layer.
        identity = get_team_identity(
            raw_name,
            api_name=raw_name,
            tournament_code=UCL_TOURNAMENT_CODE,
        )
        canonical = normalize_team_name(identity.get("name"))
        return self._index.get(canonical) if canonical else None

    def get_context(self, team_name: str | None) -> dict[str, Any] | None:
        item = self.find(team_name)
        if not item:
            return None

        rank = item.get("rank")
        return {
            "source": "uefa.com",
            "source_url": self.data.get("source_url"),
            "ranking_type": self.data.get("ranking_type", "uefa_club_coefficient"),
            "season": self.data.get("season", "2026/27"),
            "reference_period": self.data.get("reference_period", "end_of_2025_26"),
            "club": item.get("club"),
            "rank": rank,
            "rank_available": rank is not None,
            "ranking_status": item.get("ranking_status") or ("ranked" if rank is not None else "not_ranked"),
        }
