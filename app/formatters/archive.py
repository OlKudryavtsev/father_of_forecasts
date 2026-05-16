"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def format_archive_card(card: HistoricalArchiveCard) -> str:
    """Provide bot helper logic for format_archive_card."""
    tournament_title = {
        "wc2022": "ЧМ-2022",
        "euro2024": "ЧЕ-2024",
        "multi": "Архив турниров",
    }.get(card.tournament_code, "Архив турниров")

    return (
        "🔥 Архив Отца прогнозов\n\n"
        f"🏷 {card.title}\n"
        f"🗓 {tournament_title}\n\n"
        f"{card.text}"
    )

