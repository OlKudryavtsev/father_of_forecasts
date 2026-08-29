"""Sync UEFA Champions League 2026/27 fixtures from API-Football.

Run from the application environment, for example:
    python scripts/sync_ucl_2026_2027.py

Required environment:
    API_FOOTBALL_KEY
Optional environment:
    API_FOOTBALL_UCL_LEAGUE_ID=2
    API_FOOTBALL_UCL_SEASON=2026
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, ensure_schema
from app.services.tournaments import sync_ucl_2026_2027_fixtures


def main() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        result = sync_ucl_2026_2027_fixtures(db, force=True)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
