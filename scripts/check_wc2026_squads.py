#!/usr/bin/env python3
"""
Check whether WC2026 national team squads are available in API-Football.

Usage:
    API_FOOTBALL_KEY=xxx python scripts/check_wc2026_squads.py

Optional:
    API_FOOTBALL_LEAGUE_ID=1 API_FOOTBALL_SEASON=2026 python scripts/check_wc2026_squads.py

Windows PowerShell optional:
    $env:API_FOOTBALL_KEY="xxx"
    $env:PYTHONIOENCODING="utf-8"
    python scripts/check_wc2026_squads.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://v3.football.api-sports.io"
LEAGUE_ID = int(os.getenv("API_FOOTBALL_LEAGUE_ID", "1"))
SEASON = int(os.getenv("API_FOOTBALL_SEASON", "2026"))
OUTPUT_DIR = Path("tmp/api_football_wc2026_squads")


@dataclass
class TeamSquadStatus:
    team_id: int
    team_name: str
    country: str | None
    players_count: int
    goalkeepers: int
    defenders: int
    midfielders: int
    attackers: int
    unknown_positions: int
    has_squad: bool
    looks_fantasy_ready: bool
    error: str | None = None


def setup_console_encoding() -> None:
    """Make console output UTF-8 friendly on Windows."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def safe_text(value: object) -> str:
    """Return text safe for current console encoding."""
    text = str(value)

    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"

    try:
        text.encode(encoding)
        return text
    except UnicodeEncodeError:
        return text.encode(encoding, errors="replace").decode(encoding)


def api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    api_key = os.getenv("API_FOOTBALL_KEY") or os.getenv("API_SPORTS_KEY")

    if not api_key:
        raise RuntimeError(
            "Set API_FOOTBALL_KEY or API_SPORTS_KEY environment variable."
        )

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
    value = (position or "").strip().lower()

    if value in {"goalkeeper", "keeper", "gk"}:
        return "goalkeeper"

    if value in {"defender", "defence", "df"}:
        return "defender"

    if value in {"midfielder", "midfield", "mf"}:
        return "midfielder"

    if value in {"attacker", "forward", "fw"}:
        return "attacker"

    return "unknown"


def get_wc2026_teams() -> list[dict[str, Any]]:
    payload = api_get(
        "/teams",
        {
            "league": LEAGUE_ID,
            "season": SEASON,
        },
    )

    return payload.get("response", [])


def get_team_squad(team_id: int) -> list[dict[str, Any]]:
    payload = api_get(
        "/players/squads",
        {
            "team": team_id,
        },
    )

    response = payload.get("response", [])

    if not response:
        return []

    # API-Football usually returns one item:
    # {"team": {...}, "players": [...]}
    return response[0].get("players", []) or []


def check_team_squad(team_item: dict[str, Any]) -> TeamSquadStatus:
    team = team_item.get("team", {})
    team_id = int(team["id"])
    team_name = team.get("name") or str(team_id)
    country = team.get("country")

    try:
        players = get_team_squad(team_id)
    except Exception as exc:
        return TeamSquadStatus(
            team_id=team_id,
            team_name=team_name,
            country=country,
            players_count=0,
            goalkeepers=0,
            defenders=0,
            midfielders=0,
            attackers=0,
            unknown_positions=0,
            has_squad=False,
            looks_fantasy_ready=False,
            error=str(exc),
        )

    position_counts = {
        "goalkeeper": 0,
        "defender": 0,
        "midfielder": 0,
        "attacker": 0,
        "unknown": 0,
    }

    for player in players:
        position = normalize_position(player.get("position"))
        position_counts[position] += 1

    players_count = len(players)

    # Для Fantasy не обязательно строго 26 игроков,
    # но если меньше 18 — явно рано.
    looks_fantasy_ready = (
        players_count >= 18
        and position_counts["goalkeeper"] >= 2
        and position_counts["defender"] >= 4
        and position_counts["midfielder"] >= 4
        and position_counts["attacker"] >= 2
    )

    return TeamSquadStatus(
        team_id=team_id,
        team_name=team_name,
        country=country,
        players_count=players_count,
        goalkeepers=position_counts["goalkeeper"],
        defenders=position_counts["defender"],
        midfielders=position_counts["midfielder"],
        attackers=position_counts["attacker"],
        unknown_positions=position_counts["unknown"],
        has_squad=players_count > 0,
        looks_fantasy_ready=looks_fantasy_ready,
        error=None,
    )


def save_raw_team_squad(team_id: int, team_name: str) -> None:
    safe_name = "".join(
        ch if ch.isalnum() or ch in {"-", "_"} else "_"
        for ch in team_name
    )

    try:
        payload = api_get("/players/squads", {"team": team_id})
    except Exception as exc:
        payload = {"error": str(exc)}

    path = OUTPUT_DIR / "raw" / f"{team_id}_{safe_name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_summary(rows: list[TeamSquadStatus]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = OUTPUT_DIR / "summary.csv"
    json_path = OUTPUT_DIR / "summary.json"

    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "team_id",
                "team_name",
                "country",
                "players_count",
                "goalkeepers",
                "defenders",
                "midfielders",
                "attackers",
                "unknown_positions",
                "has_squad",
                "looks_fantasy_ready",
                "error",
            ],
        )
        writer.writeheader()

        for row in rows:
            writer.writerow(row.__dict__)

    json_path.write_text(
        json.dumps(
            [row.__dict__ for row in rows],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def print_report(rows: list[TeamSquadStatus]) -> None:
    total = len(rows)
    with_squad = sum(1 for row in rows if row.has_squad)
    fantasy_ready = sum(1 for row in rows if row.looks_fantasy_ready)
    errors = sum(1 for row in rows if row.error)

    print()
    print("=== WC2026 squads coverage report ===")
    print(f"League: {LEAGUE_ID}")
    print(f"Season: {SEASON}")
    print(f"Teams checked: {total}")
    print(f"Teams with any squad: {with_squad}/{total}")
    print(f"Teams fantasy-ready: {fantasy_ready}/{total}")
    print(f"Errors: {errors}")
    print()

    for row in rows:
        status = "✅ READY" if row.looks_fantasy_ready else "⚠️ NOT READY"

        if row.error:
            status = "❌ ERROR"

        print(
            f"{status:12} "
            f"{safe_text(row.team_name):24} "
            f"players={row.players_count:2} "
            f"GK={row.goalkeepers:2} "
            f"DEF={row.defenders:2} "
            f"MID={row.midfielders:2} "
            f"ATT={row.attackers:2}"
        )

        if row.error:
            print(f"             error: {safe_text(row.error)}")


def main() -> None:
    setup_console_encoding()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(
        f"Checking API-Football WC2026 teams: "
        f"league={LEAGUE_ID}, season={SEASON}"
    )

    teams = get_wc2026_teams()

    teams_path = OUTPUT_DIR / "teams.json"
    teams_path.write_text(
        json.dumps(teams, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if not teams:
        print(
            "No teams returned. Either WC2026 coverage is not available yet, "
            "or plan/season access is limited."
        )
        return

    rows: list[TeamSquadStatus] = []

    for index, team_item in enumerate(teams, start=1):
        team = team_item.get("team", {})
        team_id = team.get("id")
        team_name = team.get("name", str(team_id))

        print(f"[{index}/{len(teams)}] Checking {safe_text(team_name)}...")

        row = check_team_squad(team_item)
        rows.append(row)

        save_raw_team_squad(row.team_id, row.team_name)

        # Чтобы не упираться в rate limits на слабом тарифе.
        time.sleep(0.25)

    save_summary(rows)
    print_report(rows)

    print()
    print("Saved:")
    print(f"  {OUTPUT_DIR / 'teams.json'}")
    print(f"  {OUTPUT_DIR / 'summary.csv'}")
    print(f"  {OUTPUT_DIR / 'summary.json'}")
    print(f"  {OUTPUT_DIR / 'raw'}")


if __name__ == "__main__":
    main()