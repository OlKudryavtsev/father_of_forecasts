#!/usr/bin/env python3
"""
Check API-Football coverage for WC2026 fixtures and tournament-level endpoints.

This script checks not only fixture-level coverage, but also league/season/date
coverage for odds and API metadata that helps diagnose whether missing data is
a fixture-specific issue, a tournament issue, a date issue or a plan/coverage issue.

Main checks:
- /leagues?id=<league>&season=<season> and its coverage block
- /fixtures?league=<league>&season=<season>
- /odds?league=<league>&season=<season>
- /odds?league=<league>&season=<season>&date=<YYYY-MM-DD>
- /odds?fixture=<fixture_id>
- /bookmakers
- /bets
- /fixtures/lineups?fixture=<fixture_id>
- /fixtures/statistics?fixture=<fixture_id>
- /injuries?fixture=<fixture_id>
- /fixtures/events?fixture=<fixture_id>
- /predictions?fixture=<fixture_id>

Usage examples:

1) Check WC2026 tournament coverage from API-Football:
   API_FOOTBALL_KEY=xxx python scripts/check_api_football_wc2026_coverage.py \
     --league 1 --season 2026 --limit 10 --save-raw

2) Check fixture IDs from your DB:
   API_FOOTBALL_KEY=xxx DATABASE_URL=postgresql://... \
   python scripts/check_api_football_wc2026_coverage.py --from-db --limit 20 --save-raw

3) Check exact fixture IDs:
   API_FOOTBALL_KEY=xxx python scripts/check_api_football_wc2026_coverage.py \
     --fixture-id 1373745 --fixture-id 1373746 --save-raw

4) Check odds only:
   API_FOOTBALL_KEY=xxx python scripts/check_api_football_wc2026_coverage.py \
     --league 1 --season 2026 --endpoint odds --limit 5

Output:
- Console summary
- reports/api_football_wc2026_coverage/coverage_summary.json
- reports/api_football_wc2026_coverage/coverage_summary.csv
- reports/api_football_wc2026_coverage/coverage_summary.md
- Optional raw JSON responses in reports/api_football_wc2026_coverage/raw/
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://v3.football.api-sports.io"

DEFAULT_FIXTURE_ENDPOINTS = [
    "fixture",
    "odds",
    "lineups",
    "statistics",
    "injuries",
    "events",
    "predictions",
]

DEFAULT_TOURNAMENT_ENDPOINTS = [
    "league",
    "fixtures_by_league",
    "odds_by_league",
    "odds_by_date",
    "bookmakers",
    "bets",
]


@dataclass
class EndpointCheck:
    """Result of one API-Football endpoint check."""

    scope: str
    endpoint: str
    ok: bool
    status_code: int | None
    api_errors: Any
    results_count: int
    summary: str
    raw_saved_to: str | None = None


@dataclass
class FixtureCoverage:
    """Coverage result for a single fixture."""

    fixture_id: int
    fixture_label: str
    fixture_date: str | None
    checks: list[EndpointCheck]


@dataclass
class TournamentCoverage:
    """Coverage result for league/season/date-level endpoints."""

    league: int
    season: int
    checks: list[EndpointCheck]


class ApiFootballProbe:
    """Small API-Football client for coverage probing."""

    def __init__(
        self,
        api_key: str,
        base_url: str = BASE_URL,
        timeout: int = 30,
        sleep_seconds: float = 0.2,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call API-Football and return parsed JSON with HTTP status attached."""
        url = f"{self.base_url}/{path.lstrip('/')}"

        response = requests.get(
            url,
            headers={"x-apisports-key": self.api_key},
            params=params or {},
            timeout=self.timeout,
        )

        try:
            payload: dict[str, Any] = response.json()
        except ValueError:
            payload = {
                "get": path,
                "parameters": params or {},
                "errors": {"http": response.text[:500]},
                "results": 0,
                "response": [],
            }

        payload["_http_status_code"] = response.status_code
        payload["_request_url"] = response.url

        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)

        return payload

    def get_fixtures(self, league: int, season: int) -> list[dict[str, Any]]:
        """Fetch fixtures by league and season."""
        payload = self.get("fixtures", {"league": league, "season": season})
        ensure_no_http_error(payload, "fixtures")
        return payload.get("response") or []

    def get_fixture_ids_from_db(
        self,
        limit: int,
        tournament_code: str = "wc2026",
    ) -> list[int]:
        """Read external fixture IDs from the project's database."""
        try:
            from app.db import SessionLocal
            from app.models import Match
        except Exception as error:
            raise RuntimeError(
                "Could not import app.db/app.models. Run this script from project root "
                "or use --fixture-id / --league / --season instead."
            ) from error

        db = SessionLocal()

        try:
            rows = (
                db.query(Match.external_fixture_id)
                .filter(
                    Match.tournament_code == tournament_code,
                    Match.external_fixture_id.isnot(None),
                )
                .order_by(Match.starts_at.asc())
                .limit(limit)
                .all()
            )

            fixture_ids: list[int] = []

            for row in rows:
                value = row[0]

                if value is None:
                    continue

                try:
                    fixture_ids.append(int(value))
                except (TypeError, ValueError):
                    continue

            return fixture_ids

        finally:
            db.close()


def ensure_no_http_error(payload: dict[str, Any], label: str) -> None:
    """Raise a readable error for transport/API-level failures."""
    status_code = payload.get("_http_status_code")

    if status_code and status_code >= 400:
        raise RuntimeError(f"{label}: HTTP {status_code}: {payload}")

    errors = payload.get("errors")

    if errors:
        raise RuntimeError(f"{label}: API errors: {errors}")


def safe_count_response(payload: dict[str, Any]) -> int:
    """Return number of rows in API-Football response."""
    response = payload.get("response")

    if isinstance(response, list):
        return len(response)

    if response:
        return 1

    return 0


def has_api_errors(payload: dict[str, Any]) -> bool:
    """Return True when API-Football returned non-empty errors."""
    return bool(payload.get("errors"))


def api_ok(payload: dict[str, Any]) -> bool:
    """Return True when transport and API-level errors are absent."""
    status_code = payload.get("_http_status_code")
    return bool(status_code and status_code < 400 and not has_api_errors(payload))


def get_paging(payload: dict[str, Any]) -> dict[str, Any]:
    """Return API-Football paging block if present."""
    paging = payload.get("paging")

    if isinstance(paging, dict):
        return paging

    return {}


def summarize_fixture(payload: dict[str, Any]) -> tuple[str, str | None]:
    """Build readable label and date from /fixtures?id=... response."""
    response = payload.get("response") or []

    if not response:
        return "fixture data unavailable", None

    item = response[0]
    fixture = item.get("fixture") or {}
    teams = item.get("teams") or {}

    home = ((teams.get("home") or {}).get("name")) or "Home"
    away = ((teams.get("away") or {}).get("name")) or "Away"
    date = fixture.get("date")

    return f"{home} — {away}", date


def summarize_league(payload: dict[str, Any]) -> str:
    """Summarize /leagues?id=&season= response with coverage block."""
    rows = payload.get("response") or []

    if not rows:
        return "no league data"

    item = rows[0]
    league = item.get("league") or {}
    country = item.get("country") or {}
    seasons = item.get("seasons") or []

    season_text = "season coverage unavailable"

    if seasons:
        season = seasons[0]
        coverage = season.get("coverage") or {}
        fixtures = coverage.get("fixtures") or {}
        odds = coverage.get("odds")

        season_text = (
            f"year={season.get('year')}, start={season.get('start')}, end={season.get('end')}, "
            f"fixtures={fixtures}, standings={coverage.get('standings')}, "
            f"players={coverage.get('players')}, top_scorers={coverage.get('top_scorers')}, "
            f"injuries={coverage.get('injuries')}, predictions={coverage.get('predictions')}, "
            f"odds={odds}"
        )

    return (
        f"{league.get('name')} ({country.get('name')}), type={league.get('type')}; "
        f"{season_text}"
    )


def summarize_fixtures_by_league(payload: dict[str, Any]) -> str:
    """Summarize fixtures list for league/season."""
    rows = payload.get("response") or []

    if not rows:
        return "no fixtures"

    dates = []
    statuses: dict[str, int] = {}

    for row in rows[:200]:
        fixture = row.get("fixture") or {}
        status = fixture.get("status") or {}
        short = status.get("short") or "unknown"
        statuses[short] = statuses.get(short, 0) + 1

        date = fixture.get("date")

        if date:
            dates.append(str(date)[:10])

    date_range = "n/a"

    if dates:
        date_range = f"{min(dates)}..{max(dates)}"

    status_text = ", ".join(f"{key}={value}" for key, value in sorted(statuses.items()))

    return f"fixtures={len(rows)}, dates={date_range}, statuses={status_text}"


def summarize_odds(payload: dict[str, Any]) -> str:
    """Summarize odds response: bookmakers and common markets."""
    rows = payload.get("response") or []
    paging = get_paging(payload)
    paging_text = ""

    if paging:
        paging_text = f", paging={paging}"

    if not rows:
        return f"no odds{paging_text}"

    bookmakers_count = 0
    market_names: set[str] = set()
    fixture_ids: set[int] = set()

    for row in rows:
        fixture = row.get("fixture") or {}
        fixture_id = fixture.get("id")

        if fixture_id:
            try:
                fixture_ids.add(int(fixture_id))
            except (TypeError, ValueError):
                pass

        bookmakers = row.get("bookmakers") or []
        bookmakers_count += len(bookmakers)

        for bookmaker in bookmakers:
            for bet in bookmaker.get("bets") or []:
                market_name = bet.get("name")

                if market_name:
                    market_names.add(str(market_name))

    market_preview = ", ".join(sorted(market_names)[:8])

    if len(market_names) > 8:
        market_preview += f", +{len(market_names) - 8} more"

    return (
        f"fixtures_with_odds={len(fixture_ids)}, bookmakers={bookmakers_count}, "
        f"markets={len(market_names)} [{market_preview}]{paging_text}"
    )


def summarize_lineups(payload: dict[str, Any]) -> str:
    """Summarize lineups response."""
    rows = payload.get("response") or []

    if not rows:
        return "no lineups"

    teams = []
    starters = 0
    substitutes = 0
    formations = []

    for row in rows:
        team_name = ((row.get("team") or {}).get("name")) or "Unknown"
        teams.append(team_name)

        formation = row.get("formation")

        if formation:
            formations.append(f"{team_name}: {formation}")

        starters += len(row.get("startXI") or [])
        substitutes += len(row.get("substitutes") or [])

    return (
        f"teams={len(rows)} ({', '.join(teams)}), "
        f"starters={starters}, substitutes={substitutes}, "
        f"formations={'; '.join(formations) if formations else 'n/a'}"
    )


def summarize_statistics(payload: dict[str, Any]) -> str:
    """Summarize fixture statistics response."""
    rows = payload.get("response") or []

    if not rows:
        return "no statistics"

    stat_names: set[str] = set()

    for row in rows:
        for stat in row.get("statistics") or []:
            stat_type = stat.get("type")

            if stat_type:
                stat_names.add(str(stat_type))

    preview = ", ".join(sorted(stat_names)[:10])

    if len(stat_names) > 10:
        preview += f", +{len(stat_names) - 10} more"

    return f"teams={len(rows)}, stats={len(stat_names)} [{preview}]"


def summarize_injuries(payload: dict[str, Any]) -> str:
    """Summarize injuries response."""
    rows = payload.get("response") or []

    if not rows:
        return "no injuries"

    teams: set[str] = set()
    players = []

    for row in rows:
        team_name = ((row.get("team") or {}).get("name"))

        if team_name:
            teams.add(str(team_name))

        player_name = ((row.get("player") or {}).get("name"))

        if player_name:
            players.append(str(player_name))

    preview = ", ".join(players[:8])

    if len(players) > 8:
        preview += f", +{len(players) - 8} more"

    return f"injuries={len(rows)}, teams={len(teams)}, players=[{preview}]"


def summarize_events(payload: dict[str, Any]) -> str:
    """Summarize fixture events response."""
    rows = payload.get("response") or []

    if not rows:
        return "no events"

    types: dict[str, int] = {}

    for row in rows:
        event_type = str(row.get("type") or "unknown")
        types[event_type] = types.get(event_type, 0) + 1

    type_text = ", ".join(f"{key}={value}" for key, value in sorted(types.items()))

    return f"events={len(rows)}, {type_text}"


def summarize_predictions(payload: dict[str, Any]) -> str:
    """Summarize API-Football predictions response."""
    rows = payload.get("response") or []

    if not rows:
        return "no API prediction"

    item = rows[0]
    predictions = item.get("predictions") or {}
    percent = predictions.get("percent") or {}
    advice = predictions.get("advice")

    return (
        f"winner={((predictions.get('winner') or {}).get('name'))}, "
        f"percent={percent}, advice={advice}"
    )


def summarize_bookmakers(payload: dict[str, Any]) -> str:
    """Summarize /bookmakers response."""
    rows = payload.get("response") or []

    if not rows:
        return "no bookmakers"

    preview = ", ".join(str(row.get("name")) for row in rows[:10])

    if len(rows) > 10:
        preview += f", +{len(rows) - 10} more"

    return f"bookmakers={len(rows)} [{preview}]"


def summarize_bets(payload: dict[str, Any]) -> str:
    """Summarize /bets response."""
    rows = payload.get("response") or []

    if not rows:
        return "no bets"

    preview = ", ".join(str(row.get("name")) for row in rows[:15])

    if len(rows) > 15:
        preview += f", +{len(rows) - 15} more"

    return f"bets={len(rows)} [{preview}]"


def summarize_endpoint(endpoint: str, payload: dict[str, Any]) -> str:
    """Dispatch endpoint-specific summary."""
    if endpoint == "fixture":
        label, date = summarize_fixture(payload)
        return f"{label}, date={date}"

    if endpoint == "league":
        return summarize_league(payload)

    if endpoint == "fixtures_by_league":
        return summarize_fixtures_by_league(payload)

    if endpoint in {"odds", "odds_by_league", "odds_by_date"}:
        return summarize_odds(payload)

    if endpoint == "lineups":
        return summarize_lineups(payload)

    if endpoint == "statistics":
        return summarize_statistics(payload)

    if endpoint == "injuries":
        return summarize_injuries(payload)

    if endpoint == "events":
        return summarize_events(payload)

    if endpoint == "predictions":
        return summarize_predictions(payload)

    if endpoint == "bookmakers":
        return summarize_bookmakers(payload)

    if endpoint == "bets":
        return summarize_bets(payload)

    return f"results={safe_count_response(payload)}"


def fixture_endpoint_request(endpoint: str, fixture_id: int) -> tuple[str, dict[str, Any]]:
    """Map fixture endpoint name to API-Football path and parameters."""
    if endpoint == "fixture":
        return "fixtures", {"id": fixture_id}

    if endpoint == "odds":
        return "odds", {"fixture": fixture_id}

    if endpoint == "lineups":
        return "fixtures/lineups", {"fixture": fixture_id}

    if endpoint == "statistics":
        return "fixtures/statistics", {"fixture": fixture_id}

    if endpoint == "injuries":
        return "injuries", {"fixture": fixture_id}

    if endpoint == "events":
        return "fixtures/events", {"fixture": fixture_id}

    if endpoint == "predictions":
        return "predictions", {"fixture": fixture_id}

    raise ValueError(f"Unsupported fixture endpoint: {endpoint}")


def tournament_endpoint_request(
    endpoint: str,
    league: int,
    season: int,
    date: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Map tournament endpoint name to API-Football path and parameters."""
    if endpoint == "league":
        return "leagues", {"id": league, "season": season}

    if endpoint == "fixtures_by_league":
        return "fixtures", {"league": league, "season": season}

    if endpoint == "odds_by_league":
        return "odds", {"league": league, "season": season}

    if endpoint == "odds_by_date":
        params: dict[str, Any] = {"league": league, "season": season}

        if date:
            params["date"] = date

        return "odds", params

    if endpoint == "bookmakers":
        return "bookmakers", {}

    if endpoint == "bets":
        return "bets", {}

    raise ValueError(f"Unsupported tournament endpoint: {endpoint}")


def save_json(path: Path, payload: dict[str, Any]) -> None:
    """Save JSON with UTF-8 and indentation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def build_check(
    scope: str,
    endpoint: str,
    payload: dict[str, Any],
    output_dir: Path,
    raw_relative_path: str | None,
    save_raw: bool,
) -> EndpointCheck:
    """Build EndpointCheck and optionally save raw payload."""
    raw_saved_to = None

    if save_raw and raw_relative_path:
        raw_path = output_dir / "raw" / raw_relative_path
        save_json(raw_path, payload)
        raw_saved_to = str(raw_path)

    return EndpointCheck(
        scope=scope,
        endpoint=endpoint,
        ok=api_ok(payload),
        status_code=payload.get("_http_status_code"),
        api_errors=payload.get("errors"),
        results_count=safe_count_response(payload),
        summary=summarize_endpoint(endpoint, payload),
        raw_saved_to=raw_saved_to,
    )


def check_tournament(
    client: ApiFootballProbe,
    league: int,
    season: int,
    dates: list[str],
    endpoints: list[str],
    output_dir: Path,
    save_raw: bool,
) -> TournamentCoverage:
    """Check league/season/date-level coverage endpoints."""
    checks: list[EndpointCheck] = []

    for endpoint in endpoints:
        if endpoint == "odds_by_date":
            if not dates:
                path, params = tournament_endpoint_request(endpoint, league, season, None)
                payload = client.get(path, params)
                checks.append(
                    build_check(
                        scope="tournament",
                        endpoint=endpoint,
                        payload=payload,
                        output_dir=output_dir,
                        raw_relative_path=f"tournament/{endpoint}.json",
                        save_raw=save_raw,
                    )
                )
                continue

            for date in dates:
                path, params = tournament_endpoint_request(endpoint, league, season, date)
                payload = client.get(path, params)
                checks.append(
                    build_check(
                        scope="tournament",
                        endpoint=f"{endpoint}:{date}",
                        payload=payload,
                        output_dir=output_dir,
                        raw_relative_path=f"tournament/{endpoint}_{date}.json",
                        save_raw=save_raw,
                    )
                )

            continue

        path, params = tournament_endpoint_request(endpoint, league, season, None)
        payload = client.get(path, params)
        checks.append(
            build_check(
                scope="tournament",
                endpoint=endpoint,
                payload=payload,
                output_dir=output_dir,
                raw_relative_path=f"tournament/{endpoint}.json",
                save_raw=save_raw,
            )
        )

    return TournamentCoverage(
        league=league,
        season=season,
        checks=checks,
    )


def check_fixture(
    client: ApiFootballProbe,
    fixture_id: int,
    endpoints: list[str],
    output_dir: Path,
    save_raw: bool,
) -> FixtureCoverage:
    """Check all requested endpoints for a single fixture."""
    checks: list[EndpointCheck] = []

    fixture_label = "fixture data unavailable"
    fixture_date: str | None = None

    for endpoint in endpoints:
        path, params = fixture_endpoint_request(endpoint, fixture_id)
        payload = client.get(path, params)

        checks.append(
            build_check(
                scope="fixture",
                endpoint=endpoint,
                payload=payload,
                output_dir=output_dir,
                raw_relative_path=f"fixtures/{fixture_id}/{endpoint}.json",
                save_raw=save_raw,
            )
        )

        if endpoint == "fixture":
            fixture_label, fixture_date = summarize_fixture(payload)

    return FixtureCoverage(
        fixture_id=fixture_id,
        fixture_label=fixture_label,
        fixture_date=fixture_date,
        checks=checks,
    )


def extract_dates_from_fixtures(fixtures: list[dict[str, Any]], limit: int) -> list[str]:
    """Extract unique fixture dates from fixtures list."""
    dates: list[str] = []

    for item in fixtures:
        fixture = item.get("fixture") or {}
        date = fixture.get("date")

        if not date:
            continue

        short_date = str(date)[:10]

        if short_date not in dates:
            dates.append(short_date)

        if len(dates) >= limit:
            break

    return dates


def print_console_summary(
    tournament_coverage: TournamentCoverage | None,
    fixture_coverages: list[FixtureCoverage],
) -> None:
    """Print readable coverage summary to console."""
    print()
    print("API-Football WC2026 coverage check")
    print("=" * 90)

    if tournament_coverage:
        print()
        print(f"Tournament level: league={tournament_coverage.league}, season={tournament_coverage.season}")

        for check in tournament_coverage.checks:
            status = "OK" if check.ok else "NO/ERR"
            print(
                f"  [{status:6}] {check.endpoint:24} "
                f"results={check.results_count:<3} {check.summary}"
            )

            if check.api_errors:
                print(f"          errors={check.api_errors}")

    for coverage in fixture_coverages:
        print()
        print(f"Fixture {coverage.fixture_id}: {coverage.fixture_label}")
        if coverage.fixture_date:
            print(f"Date: {coverage.fixture_date}")

        for check in coverage.checks:
            status = "OK" if check.ok else "NO/ERR"
            print(
                f"  [{status:6}] {check.endpoint:11} "
                f"results={check.results_count:<3} {check.summary}"
            )

            if check.api_errors:
                print(f"          errors={check.api_errors}")


def write_outputs(
    tournament_coverage: TournamentCoverage | None,
    fixture_coverages: list[FixtureCoverage],
    output_dir: Path,
) -> None:
    """Write JSON, CSV and Markdown summary files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tournament": (
            {
                "league": tournament_coverage.league,
                "season": tournament_coverage.season,
                "checks": [asdict(check) for check in tournament_coverage.checks],
            }
            if tournament_coverage
            else None
        ),
        "fixtures": [
            {
                "fixture_id": coverage.fixture_id,
                "fixture_label": coverage.fixture_label,
                "fixture_date": coverage.fixture_date,
                "checks": [asdict(check) for check in coverage.checks],
            }
            for coverage in fixture_coverages
        ],
    }

    save_json(output_dir / "coverage_summary.json", payload)

    csv_path = output_dir / "coverage_summary.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "scope",
                "fixture_id",
                "fixture_label",
                "fixture_date",
                "endpoint",
                "ok",
                "status_code",
                "results_count",
                "summary",
                "api_errors",
                "raw_saved_to",
            ],
        )
        writer.writeheader()

        if tournament_coverage:
            for check in tournament_coverage.checks:
                writer.writerow(
                    {
                        "scope": check.scope,
                        "fixture_id": "",
                        "fixture_label": f"league={tournament_coverage.league}, season={tournament_coverage.season}",
                        "fixture_date": "",
                        "endpoint": check.endpoint,
                        "ok": check.ok,
                        "status_code": check.status_code,
                        "results_count": check.results_count,
                        "summary": check.summary,
                        "api_errors": json.dumps(check.api_errors, ensure_ascii=False, default=str),
                        "raw_saved_to": check.raw_saved_to,
                    }
                )

        for coverage in fixture_coverages:
            for check in coverage.checks:
                writer.writerow(
                    {
                        "scope": check.scope,
                        "fixture_id": coverage.fixture_id,
                        "fixture_label": coverage.fixture_label,
                        "fixture_date": coverage.fixture_date,
                        "endpoint": check.endpoint,
                        "ok": check.ok,
                        "status_code": check.status_code,
                        "results_count": check.results_count,
                        "summary": check.summary,
                        "api_errors": json.dumps(check.api_errors, ensure_ascii=False, default=str),
                        "raw_saved_to": check.raw_saved_to,
                    }
                )

    md_path = output_dir / "coverage_summary.md"

    lines = [
        "# API-Football WC2026 coverage check",
        "",
        f"Generated at: `{datetime.now(timezone.utc).isoformat()}`",
        "",
    ]

    if tournament_coverage:
        lines.extend(
            [
                f"## Tournament level: league={tournament_coverage.league}, season={tournament_coverage.season}",
                "",
                "| Endpoint | OK | Results | Summary |",
                "|---|---:|---:|---|",
            ]
        )

        for check in tournament_coverage.checks:
            lines.append(
                f"| `{check.endpoint}` | {'✅' if check.ok else '❌'} | "
                f"{check.results_count} | {check.summary.replace('|', '/')} |"
            )

        lines.append("")

    for coverage in fixture_coverages:
        lines.append(f"## Fixture {coverage.fixture_id}: {coverage.fixture_label}")
        if coverage.fixture_date:
            lines.append(f"Date: `{coverage.fixture_date}`")
        lines.append("")
        lines.append("| Endpoint | OK | Results | Summary |")
        lines.append("|---|---:|---:|---|")

        for check in coverage.checks:
            lines.append(
                f"| `{check.endpoint}` | {'✅' if check.ok else '❌'} | "
                f"{check.results_count} | {check.summary.replace('|', '/')} |"
            )

        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Check API-Football coverage for WC2026 fixtures and tournament endpoints.",
    )

    parser.add_argument(
        "--fixture-id",
        type=int,
        action="append",
        default=[],
        help="API-Football fixture ID. Can be passed multiple times.",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Read external fixture IDs from project DB matches table.",
    )
    parser.add_argument(
        "--tournament-code",
        default="wc2026",
        help="Tournament code for --from-db. Default: wc2026.",
    )
    parser.add_argument(
        "--league",
        type=int,
        default=1,
        help="API-Football league ID. Default: 1, usually FIFA World Cup.",
    )
    parser.add_argument(
        "--season",
        type=int,
        default=2026,
        help="API-Football season. Default: 2026.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="How many fixtures to check when using --from-db or league/season fetch.",
    )
    parser.add_argument(
        "--date-limit",
        type=int,
        default=5,
        help="How many unique match dates to check for odds_by_date. Default: 5.",
    )
    parser.add_argument(
        "--endpoint",
        action="append",
        choices=DEFAULT_FIXTURE_ENDPOINTS,
        help=(
            "Fixture endpoint to check. Can be passed multiple times. "
            f"Default: {', '.join(DEFAULT_FIXTURE_ENDPOINTS)}"
        ),
    )
    parser.add_argument(
        "--tournament-endpoint",
        action="append",
        choices=DEFAULT_TOURNAMENT_ENDPOINTS,
        help=(
            "Tournament endpoint to check. Can be passed multiple times. "
            f"Default: {', '.join(DEFAULT_TOURNAMENT_ENDPOINTS)}"
        ),
    )
    parser.add_argument(
        "--skip-tournament-checks",
        action="store_true",
        help="Do not check league/season/date-level endpoints.",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/api_football_wc2026_coverage",
        help="Directory for summary and optional raw JSON files.",
    )
    parser.add_argument(
        "--save-raw",
        action="store_true",
        help="Save raw JSON responses for every fixture/endpoint.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds. Default: 30.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Sleep between requests in seconds. Default: 0.2.",
    )

    return parser.parse_args()


def main() -> int:
    """Run coverage check."""
    args = parse_args()

    api_key = os.getenv("API_FOOTBALL_KEY") or os.getenv("APISPORTS_KEY")

    if not api_key:
        print("ERROR: set API_FOOTBALL_KEY environment variable.", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    fixture_endpoints = args.endpoint or DEFAULT_FIXTURE_ENDPOINTS
    tournament_endpoints = args.tournament_endpoint or DEFAULT_TOURNAMENT_ENDPOINTS

    client = ApiFootballProbe(
        api_key=api_key,
        timeout=args.timeout,
        sleep_seconds=args.sleep,
    )

    fixture_ids: list[int] = list(args.fixture_id)
    fixtures_from_api: list[dict[str, Any]] = []

    if args.from_db:
        fixture_ids.extend(
            client.get_fixture_ids_from_db(
                limit=args.limit,
                tournament_code=args.tournament_code,
            )
        )

    if not fixture_ids:
        print(
            f"No fixture IDs provided. Fetching fixtures for league={args.league}, "
            f"season={args.season}..."
        )

        fixtures_from_api = client.get_fixtures(args.league, args.season)

        for item in fixtures_from_api[: args.limit]:
            fixture = item.get("fixture") or {}
            fixture_id = fixture.get("id")

            if fixture_id:
                fixture_ids.append(int(fixture_id))

    if not fixtures_from_api:
        try:
            fixtures_from_api = client.get_fixtures(args.league, args.season)
        except Exception as error:
            print(f"WARNING: could not fetch fixtures for date discovery: {error}")

    dates = extract_dates_from_fixtures(fixtures_from_api, args.date_limit)

    tournament_coverage = None

    if not args.skip_tournament_checks:
        print(
            f"Checking tournament endpoints for league={args.league}, "
            f"season={args.season}, dates={dates or 'n/a'}"
        )
        tournament_coverage = check_tournament(
            client=client,
            league=args.league,
            season=args.season,
            dates=dates,
            endpoints=tournament_endpoints,
            output_dir=output_dir,
            save_raw=args.save_raw,
        )

    fixture_ids = list(dict.fromkeys(fixture_ids))

    if not fixture_ids:
        print("ERROR: no fixture IDs found.", file=sys.stderr)
        return 1

    print(f"Checking {len(fixture_ids)} fixture(s): {fixture_ids}")
    print(f"Fixture endpoints: {', '.join(fixture_endpoints)}")

    fixture_coverages = [
        check_fixture(
            client=client,
            fixture_id=fixture_id,
            endpoints=fixture_endpoints,
            output_dir=output_dir,
            save_raw=args.save_raw,
        )
        for fixture_id in fixture_ids
    ]

    print_console_summary(tournament_coverage, fixture_coverages)
    write_outputs(tournament_coverage, fixture_coverages, output_dir)

    print()
    print(f"Saved summary to: {output_dir}")
    print(f"- {output_dir / 'coverage_summary.json'}")
    print(f"- {output_dir / 'coverage_summary.csv'}")
    print(f"- {output_dir / 'coverage_summary.md'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
