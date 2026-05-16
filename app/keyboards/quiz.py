"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def build_group_quiz_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_group_quiz_keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="A",
                    callback_data=f"group_quiz_answer:{session_id}:A",
                ),
                InlineKeyboardButton(
                    text="B",
                    callback_data=f"group_quiz_answer:{session_id}:B",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="C",
                    callback_data=f"group_quiz_answer:{session_id}:C",
                ),
                InlineKeyboardButton(
                    text="D",
                    callback_data=f"group_quiz_answer:{session_id}:D",
                ),
            ],
        ]
    )


def build_quiz_keyboard(question: QuizQuestion) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_quiz_keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"A. {question.option_a}",
                    callback_data=f"quiz_answer:{question.id}:A",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"B. {question.option_b}",
                    callback_data=f"quiz_answer:{question.id}:B",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"C. {question.option_c}",
                    callback_data=f"quiz_answer:{question.id}:C",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"D. {question.option_d}",
                    callback_data=f"quiz_answer:{question.id}:D",
                )
            ],
        ]
    )

