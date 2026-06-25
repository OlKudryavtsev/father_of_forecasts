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

from app.services.gamification import normalize_humor_mode

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

PREGAME_ANALYSIS_SCHEMA = {
    "name": "father_forecasts_pregame_analysis",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "commentary": {"type": "string", "minLength": 1, "maxLength": 900},
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


def _fallback_pregame(context: dict[str, Any], mode: str) -> str:
    matches = context.get("matches") or []
    unique = context.get("unique_calls") or []
    duels = context.get("close_duels") or []
    if mode == "numbers":
        if matches:
            return f"Прогнозы раскрыты для {len(matches)} матч(а/ей). Расхождения участников отражены выше."
        return "Прогнозы раскрыты."
    if unique:
        item = unique[0]
        return (
            f"{item.get('name')} выбрал сценарий {item.get('score')} в матче «{item.get('match')}» в одиночку. "
            "Либо человек видел будущее, либо очень уверенно не видел чужие прогнозы."
        )
    if duels:
        item = duels[0]
        return (
            f"{item.get('higher_name')} и {item.get('lower_name')} идут рядом, но в прогнозах разошлись. "
            "Один матч может решить, кто будет говорить «я же чувствовал», а кто — «это был план Б»."
        )
    if matches:
        return "Лига смотрит в одну сторону. Обычно это либо коллективный разум, либо коллективное алиби."
    return "Прогнозы раскрыты. Футболу остаётся только проверить, кто здесь правда что-то понимал."


def _request_openai_commentary(
    *,
    purpose: str,
    context: dict[str, Any],
    mode: str,
    schema: dict[str, Any],
    fallback: str,
    max_chars: int,
    extra_rules: str = "",
) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    mode = normalize_humor_mode(mode)
    if not OPENAI_GAMIFICATION_ENABLED or not api_key or OpenAI is None:
        return fallback

    prompt = f"""
Ты — «Отец прогнозов», футбольный комментатор дружеской лиги.
Задача: {purpose}.
Верни только JSON по схеме.
Язык: русский.
{_tone_instruction(mode)}

Нельзя:
- выдумывать факты, числа, матчи, места, достижения, прогнозы или причины;
- давать советы по ставкам на деньги;
- атаковать личность человека или использовать оскорбления/мат;
- писать больше 3 коротких предложений, максимум {max_chars} символов;
- утверждать, что кто-то точно изменит место или наберёт очки: можно говорить только о возможной интриге, если она прямо видна в данных.
{extra_rules}

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
                    "name": schema["name"],
                    "schema": schema["schema"],
                    "strict": True,
                }
            },
        )
        payload = json.loads(response.output_text)
        text = str(payload.get("commentary") or "").strip()
        if not text:
            return fallback
        return text[:max_chars]
    except Exception as error:  # Keep notifications available during API outages.
        print(f"OpenAI gamification commentary fallback ({purpose}): {error}")
        return fallback


def _generate(kind: str, context: dict[str, Any], mode: str, personal: bool = False) -> str:
    fallback = _fallback_match(context, mode) if kind == "match" else _fallback_daily(context, mode, personal)
    purpose = (
        "Персональный итог участника после завершения матча"
        if kind == "match"
        else ("Персональный утренний итог участника" if personal else "Общий утренний итог лиги")
    )
    return _request_openai_commentary(
        purpose=purpose,
        context=context,
        mode=mode,
        schema=COMMENTARY_SCHEMA,
        fallback=fallback,
        max_chars=420,
    )


def generate_match_commentary(context: dict[str, Any], mode: str) -> str:
    return _generate("match", context, mode, personal=True)


def generate_daily_league_commentary(context: dict[str, Any], mode: str) -> str:
    return _generate("daily", context, mode, personal=False)


def generate_daily_personal_commentary(context: dict[str, Any], mode: str) -> str:
    return _generate("daily", context, mode, personal=True)


def generate_pregame_league_commentary(context: dict[str, Any], mode: str) -> str:
    """Turn a fact-only prediction slot context into a short league-chat teaser."""
    return _request_openai_commentary(
        purpose="Разбор открывшихся прогнозов участников перед стартом матча или одновременного игрового слота",
        context=context,
        mode=mode,
        schema=PREGAME_ANALYSIS_SCHEMA,
        fallback=_fallback_pregame(context, mode),
        max_chars=900,
        extra_rules=(
            "- выбери 1–3 наиболее интересных факта: единое мнение, уникальный прогноз, "
            "близкая дуэль в таблице, лидерство или форма;\n"
            "- не повторяй весь список прогнозов и таблицу: они уже будут в сообщении выше;\n"
            "- не упоминай участников, если о них нет факта в переданном контексте."
        ),
    )
