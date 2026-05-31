import json
import os
from typing import Any

from openai import OpenAI


OPENAI_FORECAST_MODEL = os.getenv("OPENAI_FORECAST_MODEL", "gpt-5.4-mini")


FORECAST_JSON_SCHEMA = {
    "name": "football_match_forecast",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "pred_home": {
                "type": "integer",
                "minimum": 0,
                "maximum": 10,
            },
            "pred_away": {
                "type": "integer",
                "minimum": 0,
                "maximum": 10,
            },
            "outcome": {
                "type": "string",
                "enum": ["home", "draw", "away"],
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
            "data_confidence": {
                "type": "string",
                "enum": ["low", "medium", "high"],
            },
            "reason": {
                "type": "string",
            },
            "key_factors": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "minItems": 2,
                "maxItems": 5,
            },
            "main_scenario": {
                "type": "string",
            },
            "alternative_scenario": {
                "type": "string",
            },
            "risk_factors": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "minItems": 1,
                "maxItems": 4,
            },
        },
        "required": [
            "pred_home",
            "pred_away",
            "outcome",
            "confidence",
            "data_confidence",
            "reason",
            "key_factors",
            "main_scenario",
            "alternative_scenario",
            "risk_factors",
        ],
    },
    "strict": True,
}


def build_forecast_prompt(context: dict[str, Any]) -> str:
    return f"""
Ты футбольный аналитик для дружеской игры прогнозов на футбол.

Задача:
- дать прогноз точного счета матча;
- выбрать исход: home/draw/away;
- вернуть только JSON по схеме;
- не использовать знания о фактическом результате матча;
- использовать только данные из контекста;
- если данных мало, опирайся на базовую силу команд, форму и осторожный футбольный счет.

Как думать:
1. Отделяй факты от интерпретации.
2. Сначала оцени базовую силу команд по FIFA ranking.
3. Затем оцени форму по последним матчам и H2H.
4. Если в external_context.odds.available=true, используй рынок букмекеров как важный, но не единственный сигнал.
5. Если в external_context.lineups.available=true, учитывай официальные составы как сильный фактор.
6. Если odds/lineups недоступны, не выдумывай котировки, составы, травмы и отсутствующих игроков.
7. В data_confidence честно оцени качество данных:
   - high: есть рейтинг, форма, H2H и доступен рынок/составы;
   - medium: есть рейтинг и форма, но нет рынка/составов;
   - low: мало фактов или много неопределенности.

Правила игры:
- 3 очка за точный счет;
- 1 очко за угаданный исход;
- поэтому лучше быть достаточно точным по исходу, но не ставить всегда 1:1.

Подсказки по счетам:
- Для сильного фаворита часто разумны 2:0, 2:1, 1:0.
- Для близких команд часто разумны 1:1, 2:1, 1:2.
- Для плей-офф близких команд ничья после игрового времени вероятнее, чем в группе.
- Не ставь экстремальные счета без веской причины.

Что вернуть:
- reason: короткий общий вывод на 2-4 предложения;
- key_factors: 2-5 конкретных факторов из контекста;
- main_scenario: наиболее вероятный сценарий матча;
- alternative_scenario: альтернативный сценарий, если игра пойдет иначе;
- risk_factors: что может сломать прогноз.

Контекст матча:
{json.dumps(context, ensure_ascii=False, indent=2)}
"""


def generate_openai_forecast(context: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)

    prompt = build_forecast_prompt(context)

    response = client.responses.create(
        model=OPENAI_FORECAST_MODEL,
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": FORECAST_JSON_SCHEMA["name"],
                "schema": FORECAST_JSON_SCHEMA["schema"],
                "strict": True,
            }
        },
    )

    data = json.loads(response.output_text)

    pred_home = int(data["pred_home"])
    pred_away = int(data["pred_away"])

    if pred_home > pred_away:
        calculated_outcome = "home"
    elif pred_away > pred_home:
        calculated_outcome = "away"
    else:
        calculated_outcome = "draw"

    if data["outcome"] != calculated_outcome:
        data["outcome"] = calculated_outcome

    return data