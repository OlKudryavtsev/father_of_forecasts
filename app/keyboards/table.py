"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def build_table_buttons_keyboard(rows: list[dict]) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_table_buttons_keyboard."""
    keyboard = []

    keyboard.append(
        [
            InlineKeyboardButton(text="№", callback_data="table_noop"),
            InlineKeyboardButton(text="Игрок", callback_data="table_noop"),
            InlineKeyboardButton(text="О", callback_data="table_noop"),
            InlineKeyboardButton(text="🎯", callback_data="table_noop"),
            InlineKeyboardButton(text="✅", callback_data="table_noop"),
            InlineKeyboardButton(text="🏆", callback_data="table_noop"),
        ]
    )

    for index, row in enumerate(rows, start=1):
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=str(index),
                    callback_data="table_noop",
                ),
                InlineKeyboardButton(
                    text=shorten_table_name(row["name"]),
                    callback_data="table_noop",
                ),
                InlineKeyboardButton(
                    text=str(row["points"]),
                    callback_data="table_noop",
                ),
                InlineKeyboardButton(
                    text=str(row["exact_scores"]),
                    callback_data="table_noop",
                ),
                InlineKeyboardButton(
                    text=str(row["outcomes"]),
                    callback_data="table_noop",
                ),
                InlineKeyboardButton(
                    text=str(row["tournament_points"]),
                    callback_data="table_noop",
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

