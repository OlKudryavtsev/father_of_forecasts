"""Real implementation extracted from the former bot_runtime monolith."""


from app.runtime import InlineKeyboardButton, InlineKeyboardMarkup, QuizQuestion

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



def build_quiz_battle_size_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for selecting the number of questions in a quiz battle."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="3 вопроса",
                    callback_data="quiz_battle_size:3",
                ),
                InlineKeyboardButton(
                    text="5 вопросов",
                    callback_data="quiz_battle_size:5",
                ),
                InlineKeyboardButton(
                    text="10 вопросов",
                    callback_data="quiz_battle_size:10",
                ),
            ]
        ]
    )


def build_quiz_battle_answer_keyboard(game_question_id: int) -> InlineKeyboardMarkup:
    """Build answer keyboard for a quiz battle question."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="A",
                    callback_data=f"quiz_battle_answer:{game_question_id}:A",
                ),
                InlineKeyboardButton(
                    text="B",
                    callback_data=f"quiz_battle_answer:{game_question_id}:B",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="C",
                    callback_data=f"quiz_battle_answer:{game_question_id}:C",
                ),
                InlineKeyboardButton(
                    text="D",
                    callback_data=f"quiz_battle_answer:{game_question_id}:D",
                ),
            ],
        ]
    )
