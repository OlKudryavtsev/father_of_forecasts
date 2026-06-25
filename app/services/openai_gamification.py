"""OpenAI wording layer for deterministic gamification facts.

The module never calculates scores or standings. It only turns already computed
facts into compact Russian football commentary and always has a template fallback.
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - deployment fallback
    OpenAI = None

from app.services.gamification import HUMOR_MODES, normalize_humor_mode

OPENAI_GAMIFICATION_MODEL = os.getenv("OPENAI_GAMIFICATION_MODEL", os.getenv("AI_MODEL", "gpt-5.5-mini"))
OPENAI_GAMIFICATION_ENABLED = os.getenv("OPENAI_GAMIFICATION_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

COMMENTARY_SCHEMA = {
    "name": "father_forecasts_commentary",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "commentary": {"type": "string", "minLength": 1, "maxLength": 420},
        },
        "required": ["commentary"],
    },
    "strict": True,
}


def _tone_instruction(mode: str) -> str:
    mode = normalize_humor_mode(mode)
    if mode == "numbers":
        return "Тон: только короткий нейтральный вывод без шуток."
    if mode == "calm":
        return "Тон: спокойный, поддерживающий, без подколов."
    if mode == "ironic":
        return "Тон: лёгкая футбольная ирония, дружелюбный подкол только футбольного решения."
    return (
        "Тон: «Без пощады» — остроумная жёсткая футбольная ирония о прогнозе, "
        "но без оскорблений человека, грубости, мата, унижений, тем про внешность, "
        "здоровье, возраст, семью, работу или личные качества."
    )


def _fallback_match(context: dict[str, Any], mode: str) -> str:
    result = context.get("result_type")
    if result == "exact":
        base = "Точный счёт. Футбол на минуту перестал спорить с твоим прогнозом."
    elif result == "outcome":
        base = "Исход прочитан верно, но детали матча снова отказались сотрудничать."
    elif result == "no_prediction":
        base = "Прогноза не было: тактика невидимки не принесла ни очков, ни объяснений."
    else:
        base = "Прогноз ушёл в офсайд. Футбол сохранил право на собственный сценарий."
    if mode == "numbers":
        return "Итог матча рассчитан по правилам лиги."
    return base


def _fallback_daily(context: dict[str, Any], mode: str, personal: bool) -> str:
    if personal:
        today = context.get("today") or {}
        points = int(today.get("points") or 0)
        if points > 0:
            return f"За сутки: {points} очк. Таблица заметила твои старания."
        return "За сутки очков нет. Статистика всё записала и сделала вид, что не осуждает."
    player = context.get("player_of_day") or {}
    if player:
        return f"Игрок дня — {player.get('name')}: {int(player.get('points') or 0)} очк. Остальным есть что пересмотреть."
    return "Матчей с итогами не было. Футбол взял паузу, таблица — нет."


def _generate(kind: str, context: dict[str, Any], mode: str, personal: bool = False) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    mode = normalize_humor_mode(mode)
    fallback = _fallback_match(context, mode) if kind == "match" else _fallback_daily(context, mode, personal)
    if not OPENAI_GAMIFICATION_ENABLED or not api_key or OpenAI is None:
        return fallback

    purpose = (
        "Персональный итог участника после завершения матча"
        if kind == "match"
        else ("Персональный утренний итог участника" if personal else "Общий утренний итог лиги")
    )
    prompt = f"""
Ты — «Отец прогнозов», футбольный комментатор дружеской лиги.
Задача: {purpose}.
Верни только JSON по схеме.
Язык: русский.
{_tone_instruction(mode)}

Нельзя:
- выдумывать факты, числа, матчи, места, достижения или причины;
- давать советы по ставкам на деньги;
- атаковать личность человека или использовать оскорбления/мат;
- обращаться к участнику на «ты», если в данных нет имени? Имя в данных есть, можно обращаться на «ты»;
- писать больше 2 коротких предложений, максимум 360 символов.

Используй только эти проверенные данные:
{json.dumps(context, ensure_ascii=False)}
"""
    try:
        client = OpenAI(api_key=api_key, timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")), max_retries=1)
        response = client.responses.create(
            model=OPENAI_GAMIFICATION_MODEL,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": COMMENTARY_SCHEMA["name"],
                    "schema": COMMENTARY_SCHEMA["schema"],
                    "strict": True,
                }
            },
        )
        payload = json.loads(response.output_text)
        text = str(payload.get("commentary") or "").strip()
        if not text:
            return fallback
        return text[:420]
    except Exception as error:  # Keep notifications available during API outages.
        print(f"OpenAI gamification commentary fallback ({kind}): {error}")
        return fallback


def generate_match_commentary(context: dict[str, Any], mode: str) -> str:
    return _generate("match", context, mode, personal=True)


def generate_daily_league_commentary(context: dict[str, Any], mode: str) -> str:
    return _generate("daily", context, mode, personal=False)


def generate_daily_personal_commentary(context: dict[str, Any], mode: str) -> str:
    return _generate("daily", context, mode, personal=True)
