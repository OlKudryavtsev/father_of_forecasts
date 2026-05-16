"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def build_matches_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_matches_keyboard."""
    buttons = []

    for match in matches:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=format_match_label(match, include_id=False),
                    callback_data=f"predict_match:{match.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_match_card_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_match_card_keyboard."""
    buttons = []

    for match in matches:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=format_match_label(match, include_id=False),
                    callback_data=f"match_card:{match.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_forecast_matches_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_forecast_matches_keyboard."""
    buttons = []

    for match in matches:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=format_match_label(match, include_id=False),
                    callback_data=f"forecast_match:{match.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)

