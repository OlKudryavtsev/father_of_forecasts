"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def build_score_keyboard(match_id: int) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_score_keyboard."""
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
        ("3:1", 3, 1),
        ("1:3", 1, 3),
    ]

    rows = []

    for index in range(0, len(common_scores), 3):
        row = []

        for label, home, away in common_scores[index:index + 3]:
            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"predict_score:{match_id}:{home}:{away}",
                )
            )

        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="Другой счет",
                callback_data=f"predict_custom:{match_id}",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_advancement_keyboard(
        match_id: int,
        pred_home: int,
        pred_away: int,
        match: Match,
) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_advancement_keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Рискнуть: пройдет {match.home_team}",
                    callback_data=(
                        f"predict_adv:{match_id}:{pred_home}:{pred_away}:home"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Рискнуть: пройдет {match.away_team}",
                    callback_data=(
                        f"predict_adv:{match_id}:{pred_home}:{pred_away}:away"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Не ставить на проход",
                    callback_data=(
                        f"predict_adv:{match_id}:{pred_home}:{pred_away}:none"
                    ),
                )
            ],
        ]
    )


def build_predictions_matches_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_predictions_matches_keyboard."""
    buttons = []

    for match in matches:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=format_match_label(match, include_id=False),
                    callback_data=f"predictions_match:{match.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)

