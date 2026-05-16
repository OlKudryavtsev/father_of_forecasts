"""Real implementation extracted from the former bot_runtime monolith."""


from app.runtime import WorldCupFact

def format_world_cup_fact(fact: WorldCupFact) -> str:
    """Provide bot helper logic for format_world_cup_fact."""
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


def format_daily_world_cup_rubric(fact: WorldCupFact) -> str:
    """Provide bot helper logic for format_daily_world_cup_rubric."""
    from app.services.facts import get_days_until_wc2026, plural_days_ru
    from app.services.quiz import build_quiz_teaser_for_fact

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
        lines.extend(
            [
                "",
                "🔥 Отец прогнозов:",
                fact.spicy_comment,
            ]
        )

    lines.extend(
        [
            "",
            "❓ Мини-вопрос:",
            build_quiz_teaser_for_fact(fact),
            "",
            "Ответ: /quiz",
        ]
    )

    return "\n".join(lines)

