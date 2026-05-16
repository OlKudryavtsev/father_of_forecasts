"""Category and tournament constants."""

from datetime import date
from pathlib import Path

WC2026_START_DATE = date(2026, 6, 11)

QUIZ_SEED_PATH = Path("data/world_cup_quiz_seed.json")

HISTORICAL_ARCHIVE_SEED_PATH = Path("data/historical_archive_seed.json")

FACT_QUIZ_CATEGORIES = {
    "any": "🎲 Любая категория",
    "wc2026": "🏆 ЧМ-2026",
    "history": "📜 История",
    "record": "📊 Рекорды",
    "team": "👥 Сборные",
    "player": "⭐ Игроки",
    "host": "🏟 Хозяева",
    "trophy": "🏆 Трофеи",
    "funny": "😂 Курьезы",
}

PLAYOFF_STAGES = {
    "round_of_32",
    "round_of_16",
    "quarterfinal",
    "semifinal",
    "third_place",
    "final",
}
