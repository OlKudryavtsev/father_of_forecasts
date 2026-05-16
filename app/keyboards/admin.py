"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def build_admin_result_matches_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_admin_result_matches_keyboard."""
    buttons = []

    for match in matches:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=format_match_label(match, include_id=False),
                    callback_data=f"admin_result_match:{match.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_admin_result_score_keyboard(match_id: int) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_admin_result_score_keyboard."""
    common_scores = [
        ("0:0", 0, 0),
        ("1:0", 1, 0),
        ("0:1", 0, 1),
        ("1:1", 1, 1),
        ("2:0", 2, 0),
        ("0:2", 0, 2),
        ("2:1", 2, 1),
        ("1:2", 1, 2),
        ("2:2", 2, 2),
        ("3:0", 3, 0),
        ("0:3", 0, 3),
        ("3:1", 3, 1),
        ("1:3", 1, 3),
        ("3:2", 3, 2),
        ("2:3", 2, 3),
    ]

    rows = []

    for index in range(0, len(common_scores), 3):
        row = []

        for label, home, away in common_scores[index:index + 3]:
            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"admin_result_score:{match_id}:{home}:{away}",
                )
            )

        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="Другой счет",
                callback_data=f"admin_result_custom:{match_id}",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_admin_result_winner_keyboard(
        match_id: int,
        score_home: int,
        score_away: int,
        match: Match,
) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_admin_result_winner_keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Прошла {match.home_team}",
                    callback_data=(
                        f"admin_result_winner:{match_id}:{score_home}:{score_away}:home"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Прошла {match.away_team}",
                    callback_data=(
                        f"admin_result_winner:{match_id}:{score_home}:{score_away}:away"
                    ),
                )
            ],
        ]
    )

