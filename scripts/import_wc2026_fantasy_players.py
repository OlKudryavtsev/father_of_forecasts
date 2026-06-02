#!/usr/bin/env python3
"""Import WC2026 fantasy players from API-Football squads.

Before running:
    psql "$DATABASE_URL" -f db/migrations/002_add_fantasy.sql

Usage:
    API_FOOTBALL_KEY=xxx python scripts/import_wc2026_fantasy_players.py

Optional:
    API_FOOTBALL_LEAGUE_ID=1 API_FOOTBALL_SEASON=2026 python scripts/import_wc2026_fantasy_players.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# Allow running as a script from project root.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal  # noqa: E402
from app.fifa_rankings import FifaRankingsStore  # noqa: E402
from app.models import FantasyPlayer  # noqa: E402
from app.services.misc import get_team_flag  # noqa: E402
from app.team_names import get_team_name_ru  # noqa: E402


BASE_URL = "https://v3.football.api-sports.io"
LEAGUE_ID = int(os.getenv("API_FOOTBALL_LEAGUE_ID", "1"))
SEASON = int(os.getenv("API_FOOTBALL_SEASON", "2026"))
TOURNAMENT_CODE = os.getenv("TOURNAMENT_CODE", "wc2026")
OUTPUT_DIR = Path("tmp/api_football_wc2026_fantasy_import")


POSITION_MAP = {
    "goalkeeper": "Goalkeeper",
    "keeper": "Goalkeeper",
    "gk": "Goalkeeper",
    "defender": "Defender",
    "defence": "Defender",
    "df": "Defender",
    "midfielder": "Midfielder",
    "midfield": "Midfielder",
    "mf": "Midfielder",
    "attacker": "Attacker",
    "forward": "Attacker",
    "fw": "Attacker",
}


def setup_console_encoding() -> None:
    """Make console output UTF-8 friendly on Windows."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call API-Football and return JSON payload."""
    api_key = os.getenv("API_FOOTBALL_KEY") or os.getenv("API_SPORTS_KEY")

    if not api_key:
        raise RuntimeError("Set API_FOOTBALL_KEY or API_SPORTS_KEY environment variable.")

    response = requests.get(
        f"{BASE_URL}{path}",
        headers={"x-apisports-key": api_key},
        params=params or {},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("errors"):
        raise RuntimeError(
            f"API returned errors for {path} {params}: "
            f"{json.dumps(payload['errors'], ensure_ascii=False)}"
        )

    return payload


def normalize_position(position: str | None) -> str:
    """Normalize API-Football position to Fantasy position."""
    return POSITION_MAP.get((position or "").strip().lower(), "Midfielder")


def fifa_category(rank: int | None) -> int:
    """Return category by FIFA rank."""
    if rank is None:
        return 4
    if rank <= 12:
        return 1
    if rank <= 24:
        return 2
    if rank <= 36:
        return 3
    return 4


def get_wc2026_teams() -> list[dict[str, Any]]:
    """Return WC2026 teams from API-Football."""
    payload = api_get("/teams", {"league": LEAGUE_ID, "season": SEASON})
    return payload.get("response", [])


def get_team_squad(team_id: int) -> list[dict[str, Any]]:
    """Return squad players for a team."""
    payload = api_get("/players/squads", {"team": team_id})
    response = payload.get("response", [])
    if not response:
        return []
    return response[0].get("players", []) or []


def import_players() -> None:
    """Import all WC2026 squad players into fantasy_players."""
    setup_console_encoding()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rankings = FifaRankingsStore()
    teams = get_wc2026_teams()
    (OUTPUT_DIR / "teams.json").write_text(
        json.dumps(teams, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if not teams:
        print("No teams returned. Stop.")
        return

    db = SessionLocal()
    imported = 0
    updated = 0
    now = datetime.now(timezone.utc)

    try:
        for index, team_item in enumerate(teams, start=1):
            team = team_item.get("team", {})
            team_id = int(team["id"])
            team_name = team.get("name") or str(team_id)
            team_display_name = get_team_name_ru(team_name)
            team_flag = get_team_flag(team_display_name, team_name)
            ranking = rankings.get_context(team_name) or rankings.get_context(team_display_name) or {}
            rank = ranking.get("rank")
            category = fifa_category(rank)

            print(f"[{index}/{len(teams)}] Import {team_name} / {team_display_name}...")
            squad = get_team_squad(team_id)

            raw_path = OUTPUT_DIR / "raw" / f"{team_id}_{team_name}.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(json.dumps(squad, ensure_ascii=False, indent=2), encoding="utf-8")

            active_external_ids: set[int] = set()

            for item in squad:
                external_player_id = int(item["id"])
                active_external_ids.add(external_player_id)
                position = normalize_position(item.get("position"))

                player = (
                    db.query(FantasyPlayer)
                    .filter(
                        FantasyPlayer.tournament_code == TOURNAMENT_CODE,
                        FantasyPlayer.external_player_id == external_player_id,
                        FantasyPlayer.external_team_id == team_id,
                    )
                    .first()
                )

                if not player:
                    player = FantasyPlayer(
                        tournament_code=TOURNAMENT_CODE,
                        external_player_id=external_player_id,
                        external_team_id=team_id,
                    )
                    db.add(player)
                    imported += 1
                else:
                    updated += 1

                player.team_name = team_name
                player.team_display_name = team_display_name
                player.team_flag = team_flag
                player.player_name = item.get("name") or str(external_player_id)
                player.age = item.get("age")
                player.number = item.get("number")
                player.position = position
                player.photo = item.get("photo")
                player.fifa_rank = rank
                player.fifa_category = category
                player.is_active = True
                player.source_updated_at = now

            # Mark players not present in the latest squad as inactive for this team.
            existing_players = (
                db.query(FantasyPlayer)
                .filter(
                    FantasyPlayer.tournament_code == TOURNAMENT_CODE,
                    FantasyPlayer.external_team_id == team_id,
                )
                .all()
            )
            for player in existing_players:
                if player.external_player_id not in active_external_ids:
                    player.is_active = False
                    player.source_updated_at = now

            db.commit()
            time.sleep(0.25)
    finally:
        db.close()

    print()
    print("Fantasy import completed")
    print(f"Imported: {imported}")
    print(f"Updated:  {updated}")
    print(f"Output:   {OUTPUT_DIR}")


if __name__ == "__main__":
    import_players()
