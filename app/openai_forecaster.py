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
            "reason": {
                "type": "string",
            },
        },
        "required": [
            "pred_home",
            "pred_away",
            "outcome",
            "confidence",
            "reason",
        ],
    },
    "strict": True,
}


def build_forecast_prompt(context: dict[str, Any]) -> str:
    return f"""
Ты футбольный аналитик для игры прогнозов.

Задача:
- дать прогноз точного счета матча;
- выбрать исход: home/draw/away;
- вернуть только JSON по схеме;
- не использовать знания о фактическом результате матча;
- использовать только данные из контекста;
- если данных мало, опирайся на базовую силу команд и осторожный футбольный счет.

Правила игры:
- 3 очка за точный счет;
- 1 очко за угаданный исход;
- поэтому лучше быть достаточно точным по исходу, но не ставить всегда 1:1.

Подсказки:
- Для сильного фаворита часто разумны 2:0, 2:1, 1:0.
- Для близких команд часто разумны 1:1, 2:1, 1:2.
- Для плей-офф близких команд ничья после игрового времени вероятнее, чем в группе.
- Не ставь экстремальные счета без веской причины.
- Используй FIFA ranking перед турниром как сильный сигнал базового уровня команды.
- Если FIFA ranking недоступен, используй Elo ranking как основной сигнал базовой силы команды.
- Elo ranking обычно полезен как оценка относительной силы сборных.
- Используй последние матчи до турнира для оценки формы до старта.
- Используй квалификационную статистику для понимания качества отбора, но не переоценивай ее: разные зоны отбора отличаются по силе.
- Если pre-tournament данные противоречат форме внутри турнира, то ближе к поздним стадиям турнира больше доверяй форме внутри турнира.
- Если FIFA ranking содержит total_points=null, используй только rank. Меньший rank означает более сильную команду. Не считай отсутствие points слабостью команды.

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