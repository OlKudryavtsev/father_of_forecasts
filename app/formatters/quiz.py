"""Real implementation extracted from the former bot_runtime monolith."""


from app.constants.categories import FACT_QUIZ_CATEGORIES
from app.runtime import QuizQuestion

def format_group_quiz_question(question: QuizQuestion) -> str:
    """Provide bot helper logic for format_group_quiz_question."""
    category_text = FACT_QUIZ_CATEGORIES.get(
        question.category or "any",
        question.category or "История ЧМ",
    )

    year_text = (
        f"ЧМ-{question.tournament_year}"
        if question.tournament_year
        else "История ЧМ"
    )

    return (
        "❓ Квиз от Отца прогнозов\n\n"
        f"Категория: {category_text}\n"
        f"Тема: {year_text}\n\n"
        f"{question.question_text}\n\n"
        f"A) {question.option_a}\n"
        f"B) {question.option_b}\n"
        f"C) {question.option_c}\n"
        f"D) {question.option_d}\n\n"
        "Отвечайте кнопками ниже. Ответы пока скрыты."
    )


def format_quiz_question(question: QuizQuestion) -> str:
    """Provide bot helper logic for format_quiz_question."""
    year_text = f"ЧМ-{question.tournament_year}" if question.tournament_year else "История ЧМ"

    return (
        "❓ Мини-вопрос от Отца прогнозов\n\n"
        f"🗓 {year_text}\n"
        f"🏷 {question.category or 'history'}\n\n"
        f"{question.question_text}"
    )

