"""Format World Cup facts and daily fact rubric messages."""

from app.runtime import HistoricalArchiveCard, WorldCupFact


def format_world_cup_fact(fact: WorldCupFact) -> str:
    """Format a manually requested World Cup fact."""
    year_text = f"ЧМ-{fact.tournament_year}" if fact.tournament_year else "История ЧМ"

    lines = [
        "📚 Факт от Отца прогнозов",
        "",
        f"🏷 {fact.title}",
        f"🗓 {year_text}",
        "",
        fact.fact_text,
    ]

    if fact.spicy_comment:
        lines.extend(["", f"🔥 {fact.spicy_comment}"])

    return "\n".join(lines)


def format_daily_world_cup_rubric(
    fact: WorldCupFact,
    archive_card: HistoricalArchiveCard | None = None,
) -> str:
    """Format the daily World Cup rubric without a low-value mini-question."""
    from app.services.facts import get_days_until_wc2026, plural_days_ru

    days_left = get_days_until_wc2026()

    if days_left == 0:
        countdown_text = "⏳ ЧМ-2026 стартует сегодня!"
    else:
        day_word = plural_days_ru(days_left)
        countdown_text = f"⏳ До ЧМ-2026 осталось {days_left} {day_word}"

    lines = [
        countdown_text,
        "",
        "📚 Факт дня:",
        fact.fact_text,
    ]

    if fact.spicy_comment:
        lines.extend(["", "🔥 Отец прогнозов:", fact.spicy_comment])

    if archive_card:
        lines.extend(["", "🗂 Архив Отца прогнозов:", archive_card.title, archive_card.text])

    lines.extend(
        [
            "",
            "🎮 Еще интересные факты и вопросы:",
            "— квиз-баттл в группе: /quiz_battle",
            "— быстрый квиз: /quiz",
            "— случайный факт о ЧМ: /fact",
            "— карточка из архива: /archive",
        ]
    )

    return "\n".join(lines)
