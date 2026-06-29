"""Forecast service for the Father Predictions bot."""

from __future__ import annotations

from typing import Any

from app.formatters.matches import (
    format_datetime,
    format_h2h_fact,
    format_match_label,
    format_ranking_fact,
    format_short_matches_fact,
)
from app.runtime import Match, User, build_wc2026_openai_context, generate_openai_forecast
from app.constants.categories import PLAYOFF_STAGES


def is_forecast_bot_user(user: User) -> bool:
    """Return True for the internal forecast-bot pseudo user."""
    return getattr(user, "telegram_id", None) == 0


def _format_bullets(items: list[str] | None, fallback: str = "—") -> str:
    """Format short bullet list for Telegram."""
    clean_items = [str(item).strip() for item in (items or []) if str(item).strip()]

    if not clean_items:
        return fallback

    return "\n".join(f"— {item}" for item in clean_items)


def _format_odds_context(external_context: dict[str, Any]) -> str | None:
    """Format optional bookmaker odds block, only when odds are available."""
    odds = (external_context or {}).get("odds") or {}

    if not odds.get("available"):
        return None

    lines = [
        "📈 Рынок букмекеров",
    ]

    bookmakers_count = odds.get("bookmakers_count")

    if bookmakers_count:
        lines.append(f"Букмекеров в выборке: {bookmakers_count}")

    markets = odds.get("markets") or {}

    if not markets:
        return None

    for market_name, market in list(markets.items())[:3]:
        values = market.get("values") or {}

        if not values:
            continue

        value_parts = []

        for label, value in list(values.items())[:4]:
            avg_odds = value.get("avg_odds")
            implied_probability = value.get("implied_probability")

            if avg_odds is None:
                continue

            if implied_probability is not None:
                value_parts.append(
                    f"{label}: {avg_odds} (~{int(float(implied_probability) * 100)}%)"
                )
            else:
                value_parts.append(f"{label}: {avg_odds}")

        if value_parts:
            lines.append(f"{market_name}: " + "; ".join(value_parts))

    if len(lines) <= 1:
        return None

    return "\n".join(lines)


def _format_lineups_context(external_context: dict[str, Any]) -> str | None:
    """Format optional official lineups block, only when lineups are available."""
    lineups = (external_context or {}).get("lineups") or {}

    if not lineups.get("available"):
        return None

    teams = lineups.get("teams") or []

    if not teams:
        return None

    lines = [
        "👥 Официальные составы",
    ]

    for team in teams[:2]:
        starters = team.get("starters") or []
        starters_text = ", ".join(starters[:6])

        if len(starters) > 6:
            starters_text += ", ..."

        formation = team.get("formation") or "схема не указана"

        lines.append(
            f"{team.get('team')}: {formation}"
            + (f"; в старте: {starters_text}" if starters_text else "")
        )

    return "\n".join(lines)


def _format_data_confidence(value: str | None) -> str:
    """Convert model data-confidence enum to Russian label."""
    return {
        "high": "высокая",
        "medium": "средняя",
        "low": "низкая",
    }.get(value or "", "средняя")


def build_forecast_text(db, match: Match) -> str:
    """Build a structured AI forecast text for Telegram and Mini App."""
    context = build_wc2026_openai_context(db, match)
    forecast = generate_openai_forecast(context)

    pred_home = int(forecast["pred_home"])
    pred_away = int(forecast["pred_away"])

    is_playoff = str(getattr(match, "stage", "") or "").lower() in PLAYOFF_STAGES
    advancement_enabled = bool(forecast.get("advancement_bet_enabled")) if is_playoff else False
    advancing_side = str(forecast.get("predicted_advancing_side") or "").lower().strip()
    if advancing_side not in {"home", "away"}:
        advancing_side = ""
    if not advancement_enabled or not advancing_side:
        advancement_enabled = False
        advancing_side = ""
    advancement_text = ""
    if is_playoff:
        if advancement_enabled:
            advancing_team = match.home_team if advancing_side == "home" else match.away_team
            advancement_text = f"Прогноз на проход: {advancing_team}\n"
        else:
            advancement_text = "Прогноз на проход: не указан\n"

    outcome_text = {
        "home": f"победа {match.home_team}",
        "away": f"победа {match.away_team}",
        "draw": "ничья",
    }[forecast["outcome"]]

    confidence = int(float(forecast["confidence"]) * 100)
    data_confidence = _format_data_confidence(forecast.get("data_confidence"))

    fixture = context["fixture"]

    home_api_name = fixture["home_team_api_name"]
    away_api_name = fixture["away_team_api_name"]

    rankings = context.get("fifa_rankings_sofascore") or {}
    recent_short = context.get("recent_matches_short") or {}
    h2h = context.get("head_to_head") or {}
    external_context = context.get("external_context") or {}

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

    optional_blocks = []

    odds_text = _format_odds_context(external_context)
    lineups_text = _format_lineups_context(external_context)

    if odds_text:
        optional_blocks.append(odds_text)

    if lineups_text:
        optional_blocks.append(lineups_text)

    optional_text = ("\n\n".join(optional_blocks) + "\n\n") if optional_blocks else ""

    return (
        "🤖 Прогноз Отца прогнозов\n\n"
        f"{format_match_label(match, include_id=True)}\n"
        f"Старт: {format_datetime(match.starts_at)}\n\n"
        f"Прогноз счета: {pred_home}:{pred_away}\n"
        f"{advancement_text}"
        f"Исход: {outcome_text}\n"
        f"Уверенность: {confidence}%\n"
        f"Качество данных: {data_confidence}\n\n"
        "🧠 Логика прогноза\n"
        f"{forecast.get('reason', '')}\n\n"
        "🔎 Ключевые факторы\n"
        f"{_format_bullets(forecast.get('key_factors'))}\n\n"
        "🎬 Сценарии матча\n"
        f"Базовый: {forecast.get('main_scenario', 'нет данных')}\n"
        f"Альтернативный: {forecast.get('alternative_scenario', 'нет данных')}\n\n"
        "⚠️ Что может сломать прогноз\n"
        f"{_format_bullets(forecast.get('risk_factors'))}\n\n"
        f"{optional_text}"
        f"{facts_text}\n\n"
        "Это развлекательный прогноз по футбольным данным и ИИ-анализу, "
        "не гарантия результата."
    )
