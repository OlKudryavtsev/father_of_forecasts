import os

from openai import OpenAI


AI_MODEL = os.getenv("AI_MODEL", "gpt-5.5-mini")


def build_ai_summary_prompt(context: dict) -> str:
    return f"""
Ты — футбольный Telegram-бот «Отец прогнозов».

Нужно написать короткий, живой и дружеский анализ статистики участника.
Стиль: ироничный, но не оскорбительный.
Язык: русский.
Длина: 6-10 предложений.
Не выдумывай факты, используй только данные из JSON.
Не упоминай, что получил JSON.
Не давай букмекерских советов и не говори о ставках на деньги.

Данные участника:
{context}
"""


def generate_ai_summary(context: dict) -> str:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return (
            "ИИ-сводка пока не настроена: не задан OPENAI_API_KEY. "
            "Обычная статистика доступна через /summary."
        )

    client = OpenAI(api_key=api_key)

    prompt = build_ai_summary_prompt(context)

    response = client.responses.create(
        model=AI_MODEL,
        input=prompt,
    )

    return response.output_text.strip()