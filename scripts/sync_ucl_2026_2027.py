"""Sync UEFA Champions League 2026/27 league-phase fixtures.

Run from the application environment, for example:
    python scripts/sync_ucl_2026_2027.py

Required environment:
    API_FOOTBALL_KEY
Optional environment:
    API_FOOTBALL_UCL_LEAGUE_ID=2
    API_FOOTBALL_UCL_SEASON=2026

The provider feed may include qualifying/play-off rounds.  After the provider
sync, this script normalizes provider aliases, removes non-league-phase matches
and normalizes the 144 confirmed league-phase fixtures to the official UEFA
dates and Russian club names.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, ensure_schema
from app.services.tournaments import sync_ucl_2026_2027_fixtures
from app.services.ucl_2026_2027 import apply_ucl_league_phase_cleanup
from app.services.ucl_provider_aliases import apply_ucl_provider_aliases


def main() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        sync_result = sync_ucl_2026_2027_fixtures(db, force=True)
        alias_result = apply_ucl_provider_aliases(db)
        cleanup_result = apply_ucl_league_phase_cleanup(db)
        print({
            "sync": sync_result,
            "provider_aliases": alias_result,
            "league_phase_cleanup": cleanup_result,
        })
    finally:
        db.close()


if __name__ == "__main__":
    main()
