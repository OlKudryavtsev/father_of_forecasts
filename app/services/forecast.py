"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def is_forecast_bot_user(user: User) -> bool:
    """Provide bot helper logic for is_forecast_bot_user."""
    return getattr(user, "telegram_id", None) == 0


def build_forecast_text(db, match: Match) -> str:
    """Provide bot helper logic for build_forecast_text."""
    context = build_wc2026_openai_context(db, match)

    forecast = generate_openai_forecast(context)

    pred_home = int(forecast["pred_home"])
    pred_away = int(forecast["pred_away"])

    outcome_text = {
        "home": f"победа {match.home_team}",
        "away": f"победа {match.away_team}",
        "draw": "ничья",
    }[forecast["outcome"]]

    confidence = int(float(forecast["confidence"]) * 100)

    fixture = context["fixture"]

    home_api_name = fixture["home_team_api_name"]
    away_api_name = fixture["away_team_api_name"]

    rankings = context.get("fifa_rankings_sofascore") or {}
    recent_short = context.get("recent_matches_short") or {}
    h2h = context.get("head_to_head") or {}

    ranking_home = rankings.get(home_api_name)
    ranking_away = rankings.get(away_api_name)

    recent_home = recent_short.get(home_api_name, [])
    recent_away = recent_short.get(away_api_name, [])

    h2h_rows = h2h.get("matches_short", [])

    facts_text = (
        "📌 Факты перед матчем\n\n"
        "FIFA ranking:\n"
        f"{format_ranking_fact(match.home_team, ranking_home)}\n"
        f"{format_ranking_fact(match.away_team, ranking_away)}\n\n"
        "Последние 3 матча:\n"
        f"{format_short_matches_fact(match.home_team, recent_home)}\n\n"
        f"{format_short_matches_fact(match.away_team, recent_away)}\n\n"
        "Личные встречи:\n"
        f"{format_h2h_fact(h2h_rows)}"
    )

    return (
        "🤖 Прогноз Отца прогнозов\n\n"
        f"{format_match_label(match, include_id=True)}\n"
        f"Старт: {format_datetime(match.starts_at)}\n\n"
        f"Прогноз счета: {pred_home}:{pred_away}\n"
        f"Исход: {outcome_text}\n"
        f"Уверенность: {confidence}%\n\n"
        f"{forecast.get('reason', '')}\n\n"
        f"{facts_text}\n\n"
        "Это развлекательный прогноз по футбольным данным и ИИ-анализу, "
        "не гарантия результата."
    )

