"""Static Father Forecast for WC2026 tournament outcomes."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "father_tournament_forecast_wc2026.json"


@lru_cache(maxsize=1)
def load_father_tournament_forecast() -> dict[str, Any]:
    """Load static Father Forecast data from JSON seed file."""
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def get_top_scorer_candidates() -> list[dict[str, Any]]:
    """Return top scorer candidates for Mini App dropdowns and hints."""
    data = load_father_tournament_forecast()
    return list(data.get("top_scorer_candidates") or [])


def get_top_scorer_hint() -> str:
    """Return short hint explaining how to choose a top scorer."""
    data = load_father_tournament_forecast()
    return str(data.get("top_scorer_hint") or "")


def build_father_tournament_forecast_text() -> str:
    """Format static Father Forecast for Telegram messages."""
    data = load_father_tournament_forecast()
    forecast = data.get("forecast") or {}
    confidence = data.get("confidence") or {}
    alternatives = data.get("alternatives") or {}
    reasoning = data.get("reasoning") or []

    lines = [
        "🤖 Прогноз Отца на ЧМ-2026",
        "",
        f"🏆 Чемпион: {forecast.get('champion', '—')}",
        f"🥈 Финалист: {forecast.get('runner_up', '—')}",
        f"🥉 3 место: {forecast.get('third_place', '—')}",
        f"⚽ Лучший бомбардир: {forecast.get('top_scorer', '—')}",
        "",
        "Почему так:",
    ]

    for item in reasoning:
        lines.append(f"— {item}")

    lines.extend([
        "",
        "Уверенность:",
        f"— Франция чемпион: {confidence.get('champion', '—')}",
        f"— Испания финал: {confidence.get('runner_up', '—')}",
        f"— Бразилия в топ-3: {confidence.get('third_place', '—')}",
        f"— Мбаппе бомбардир: {confidence.get('top_scorer', '—')}",
        "",
        "Альтернативы:",
        f"🏆 Чемпион: {', '.join(alternatives.get('champion') or [])}",
        f"🥈 Финалист: {', '.join(alternatives.get('runner_up') or [])}",
        f"🥉 3 место: {', '.join(alternatives.get('third_place') or [])}",
        f"⚽ Бомбардир: {', '.join(alternatives.get('top_scorer') or [])}",
        "",
        "⚠️ Качество данных:",
        str(data.get("data_quality") or "—"),
        "",
        "🔥 Вердикт Отца:",
        str(data.get("spicy_comment") or "—"),
    ])

    return "\n".join(lines)


def serialize_father_tournament_forecast() -> dict[str, Any]:
    """Return JSON-serializable Father Forecast payload for Mini App."""
    data = load_father_tournament_forecast()
    return {
        "tournament_code": data.get("tournament_code"),
        "version": data.get("version"),
        "updated_at": data.get("updated_at"),
        "forecast": data.get("forecast") or {},
        "confidence": data.get("confidence") or {},
        "alternatives": data.get("alternatives") or {},
        "reasoning": data.get("reasoning") or [],
        "data_quality": data.get("data_quality"),
        "spicy_comment": data.get("spicy_comment"),
        "top_scorer_hint": data.get("top_scorer_hint"),
    }
