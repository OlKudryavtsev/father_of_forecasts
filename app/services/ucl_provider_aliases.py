"""Provider alias fixes for UCL 2026/27 API-Football imports.

API-Football may expose the Azerbaijan club as ``Sabah FA`` while the official
league-phase helper uses the canonical name ``Sabah``.  The main cleanup step
matches fixtures by canonical team pairs, so provider-only aliases must be
normalized before applying the official fixture map.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Match
from app.services.ucl_2026_2027 import UCL_2026_2027_CODE

PROVIDER_TEAM_ALIASES: dict[str, str] = {
    "Sabah FA": "Sabah",
    "Sabah FK": "Sabah",
}


def _alias(value: str | None) -> str | None:
    if value in PROVIDER_TEAM_ALIASES:
        return PROVIDER_TEAM_ALIASES[value]
    return value


def apply_ucl_provider_aliases(db: Session) -> dict[str, Any]:
    """Normalize known provider aliases before league-phase cleanup."""
    matches = db.query(Match).filter(Match.tournament_code == UCL_2026_2027_CODE).all()
    changed = 0
    touched_ids: list[int] = []

    for match in matches:
        before = (
            match.home_team,
            match.away_team,
            match.home_team_api_name,
            match.away_team_api_name,
        )
        match.home_team = _alias(match.home_team) or match.home_team
        match.away_team = _alias(match.away_team) or match.away_team
        match.home_team_api_name = _alias(match.home_team_api_name) or match.home_team_api_name
        match.away_team_api_name = _alias(match.away_team_api_name) or match.away_team_api_name
        after = (
            match.home_team,
            match.away_team,
            match.home_team_api_name,
            match.away_team_api_name,
        )
        if after != before:
            changed += 1
            if match.id is not None:
                touched_ids.append(int(match.id))

    if changed:
        db.commit()

    return {
        "status": "ok",
        "changed_matches": changed,
        "aliases": PROVIDER_TEAM_ALIASES,
        "touched_match_ids": touched_ids[:20],
    }
