"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def import_historical_archive_from_seed(db) -> dict:
    """Provide bot helper logic for import_historical_archive_from_seed."""
    if not HISTORICAL_ARCHIVE_SEED_PATH.exists():
        raise FileNotFoundError(
            f"Файл не найден: {HISTORICAL_ARCHIVE_SEED_PATH}"
        )

    payload = json.loads(
        HISTORICAL_ARCHIVE_SEED_PATH.read_text(encoding="utf-8")
    )

    cards = payload.get("cards", [])

    created = 0
    updated = 0
    skipped = 0

    for item in cards:
        external_id = item.get("id")

        if not external_id:
            skipped += 1
            continue

        card = db.query(HistoricalArchiveCard).filter(
            HistoricalArchiveCard.external_id == external_id
        ).first()

        if not card:
            card = HistoricalArchiveCard(external_id=external_id)
            db.add(card)
            created += 1
        else:
            updated += 1

        card.title = item.get("title") or "Архив Отца прогнозов"
        card.text = item.get("text") or ""
        card.card_type = item.get("card_type")
        card.tournament_code = item.get("tournament_code")
        card.related_name = item.get("related_name")
        card.related_telegram_id = item.get("related_telegram_id")
        card.is_public = bool(item.get("is_public", True))
        card.is_active = bool(item.get("is_active", True))

    db.commit()

    return {
        "total": len(cards),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }

