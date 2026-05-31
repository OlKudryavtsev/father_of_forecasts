"""API-Football coverage monitoring for WC2026 forecast inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.api_football import ApiFootballClient
from app.models import Match
from app.runtime import TOURNAMENT_CODE


@dataclass(frozen=True)
class FixtureCoverageRow:
    """Coverage status for one match fixture."""

    match_id: int
    fixture_id: str
    label: str
    starts_at: datetime
    fixture_ok: bool
    odds_count: int
    lineups_count: int
    predictions_count: int
    injuries_count: int
    errors: list[str]


def _safe_response_count(
    api_client: ApiFootballClient,
    path: str,
    params: dict[str, Any],
) -> tuple[int, str | None]:
    """Return response count for an API-Football endpoint without raising."""
    try:
        payload = api_client.get(path, params=params)
    except Exception as error:
        return 0, str(error)

    response = payload.get("response")

    if isinstance(response, list):
        return len(response), None

    if response:
        return 1, None

    return 0, None


def _format_match_label(match: Match) -> str:
    """Build compact label for coverage reports."""
    return f"#{match.id}. {match.home_team} — {match.away_team}"


def check_wc2026_api_coverage(
    db: Session,
    limit: int = 10,
) -> list[FixtureCoverageRow]:
    """Check whether optional forecast inputs exist for upcoming WC2026 matches."""
    now = datetime.now(timezone.utc)
    api_client = ApiFootballClient()

    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.starts_at >= now,
            Match.external_fixture_id.isnot(None),
        )
        .order_by(Match.starts_at.asc())
        .limit(limit)
        .all()
    )

    rows: list[FixtureCoverageRow] = []

    for match in matches:
        fixture_id = str(match.external_fixture_id)
        errors: list[str] = []

        fixture_count, fixture_error = _safe_response_count(
            api_client,
            "/fixtures",
            {"id": fixture_id},
        )

        if fixture_error:
            errors.append(f"fixture: {fixture_error}")

        odds_count, odds_error = _safe_response_count(
            api_client,
            "/odds",
            {"fixture": fixture_id},
        )

        if odds_error:
            errors.append(f"odds: {odds_error}")

        lineups_count, lineups_error = _safe_response_count(
            api_client,
            "/fixtures/lineups",
            {"fixture": fixture_id},
        )

        if lineups_error:
            errors.append(f"lineups: {lineups_error}")

        predictions_count, predictions_error = _safe_response_count(
            api_client,
            "/predictions",
            {"fixture": fixture_id},
        )

        if predictions_error:
            errors.append(f"predictions: {predictions_error}")

        injuries_count, injuries_error = _safe_response_count(
            api_client,
            "/injuries",
            {"fixture": fixture_id},
        )

        if injuries_error:
            errors.append(f"injuries: {injuries_error}")

        rows.append(
            FixtureCoverageRow(
                match_id=match.id,
                fixture_id=fixture_id,
                label=_format_match_label(match),
                starts_at=match.starts_at,
                fixture_ok=fixture_count > 0,
                odds_count=odds_count,
                lineups_count=lineups_count,
                predictions_count=predictions_count,
                injuries_count=injuries_count,
                errors=errors,
            )
        )

    return rows


def build_api_coverage_report(db: Session, limit: int = 10) -> list[str]:
    """Build a Telegram-friendly report for optional API-Football forecast inputs."""
    rows = check_wc2026_api_coverage(db=db, limit=limit)

    if not rows:
        return [
            "📡 API-Football coverage WC2026",
            "",
            "Не нашел будущие матчи с external_fixture_id.",
        ]

    checked = len(rows)
    fixture_ok = sum(1 for row in rows if row.fixture_ok)
    odds_ok = sum(1 for row in rows if row.odds_count > 0)
    lineups_ok = sum(1 for row in rows if row.lineups_count > 0)
    predictions_ok = sum(1 for row in rows if row.predictions_count > 0)
    injuries_ok = sum(1 for row in rows if row.injuries_count > 0)
    errors_count = sum(1 for row in rows if row.errors)

    lines = [
        "📡 API-Football coverage WC2026",
        "",
        f"Проверено матчей: {checked}",
        "",
        f"Fixtures: {fixture_ok}/{checked}",
        f"Odds: {odds_ok}/{checked}",
        f"Lineups: {lineups_ok}/{checked}",
        f"Predictions: {predictions_ok}/{checked}",
        f"Injuries: {injuries_ok}/{checked}",
        f"Ошибки API: {errors_count}/{checked}",
        "",
    ]

    if odds_ok > 0 or lineups_ok > 0:
        lines.extend(
            [
                "✅ Появились новые данные для расширенного forecast.",
                "Можно включать и проверять Forecast v2 на конкретных матчах.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Вывод:",
                "Расширенный forecast по odds/lineups пока включать как обязательный фактор рано.",
                "Каркас уже готов: когда данные появятся, они будут использоваться автоматически.",
                "",
            ]
        )

    lines.append("Детали по матчам:")

    for row in rows:
        parts = [
            f"fixture={'✅' if row.fixture_ok else '❌'}",
            f"odds={row.odds_count}",
            f"lineups={row.lineups_count}",
            f"pred={row.predictions_count}",
            f"inj={row.injuries_count}",
        ]

        lines.append(f"{row.label}: " + ", ".join(parts))

        if row.errors:
            lines.append("  ⚠️ " + " | ".join(row.errors[:2]))

    return lines
