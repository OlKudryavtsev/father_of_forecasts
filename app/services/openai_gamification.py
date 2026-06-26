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

# Reuse the proven forecast model by default. This avoids silently falling
# back to templates when a separate gamification model was not configured.
OPENAI_GAMIFICATION_MODEL = (
    os.getenv("OPENAI_GAMIFICATION_MODEL")
    or os.getenv("OPENAI_FORECAST_MODEL")
    or os.getenv("AI_MODEL")
    or "gpt-5.4-mini"
)
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


def _pregame_variant_index(context: dict[str, Any], size: int) -> int:
    seed = str(context.get("style_seed") or "pregame")
    return sum((index + 1) * ord(char) for index, char in enumerate(seed)) % max(1, size)


def _fallback_pregame(context: dict[str, Any], mode: str) -> str:
    """Write a varied group-level fallback when OpenAI is unavailable.

    The fallback intentionally talks about the league's overall pattern rather
    than repeatedly roasting one participant with a unique prediction.
    """
    matches = context.get("matches") or []
    duels = context.get("close_duels") or []
    if mode == "numbers":
        if matches:
            return f"Прогнозы раскрыты для {len(matches)} матч(а/ей). Распределение сценариев показано выше."
        return "Прогнозы раскрыты."
    if not matches:
        return "Прогнозы раскрыты. Футболу остаётся только проверить, кто здесь правда что-то понимал."

    total_unique = sum(
        1
        for match in matches
        for group in (match.get("score_groups") or [])
        if int(group.get("count") or 0) == 1
    )
    consensus = [match for match in matches if match.get("consensus_score")]
    rich_match = max(
        matches,
        key=lambda item: len(item.get("score_groups") or []),
    )
    group_count = len(rich_match.get("score_groups") or [])
    label = rich_match.get("label") or "этот матч"
    dominant = (rich_match.get("score_groups") or [{}])[0]
    dominant_score = dominant.get("score")
    dominant_count = int(dominant.get("count") or 0)

    openings = [
        "Коллективный штаб лиги сдал протокол: прогнозы есть, общего плана — не у всех.",
        "Лига открыла карты и внезапно выяснила, что футбольная интуиция умеет работать в разных режимах.",
        "Прогнозный штаб собрался. Единственное, чего он пока не собрал, — единая версия происходящего.",
        "Карты на столе: часть лиги строит расчёт, часть — красивую легенду для послематчевого чата.",
    ]
    sentences = [openings[_pregame_variant_index(context, len(openings))]]

    if consensus:
        consensus_labels = ", ".join(
            f"{item.get('label')} — {item.get('consensus_score')}" for item in consensus[:2]
        )
        sentences.append(
            f"По {consensus_labels} лига выступила единым организмом: либо коллективный разум, либо коллективное алиби."
        )
    elif group_count <= 1 and dominant_score:
        sentences.append(
            f"В матче «{label}» все голоса сошлись на {dominant_score}; альтернативный сценарий сегодня остался без профсоюза."
        )
    elif dominant_score:
        sentences.append(
            f"В матче «{label}» самый популярный сценарий — {dominant_score} ({dominant_count}), но вариантов уже {group_count}: дисциплина уступила место творческому беспорядку."
        )

    if total_unique:
        sentences.append(
            f"В слоте есть {total_unique} одиночных сценария: лига оставила футболу достаточно поводов выбрать самый неудобный из них."
        )
    elif duels:
        duel = duels[0]
        sentences.append(
            f"Особенно нервно у соседей по таблице: #{duel.get('higher_rank')} и #{duel.get('lower_rank')} расходятся в прогнозах при разнице всего {duel.get('points_gap')} очк."
        )

    return " ".join(sentences[:3])


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
            "- напиши единый мини-обзор всей лиги и игрового слота, а не портрет одного участника;\n"
            "- начни с коллективного рисунка прогнозов: единодушие, раскол, фаворитский сценарий, число разных счетов или дуэль в таблице;\n"
            "- одиночные прогнозы можно упомянуть только как часть общей картины, не делай из одного человека героя всего текста;\n"
            "- не повторяй весь список прогнозов и таблицу: они уже будут в сообщении выше;\n"
            "- не используй и не перефразируй шаблон «либо человек видел будущее, либо очень уверенно не видел чужие прогнозы»;\n"
            "- используй style_seed как внутренний ключ для свежей подачи: меняй образ, ритм и шутку между игровыми слотами;\n"
            "- не упоминай участников, если о них нет факта в переданном контексте."
        ),
    )
