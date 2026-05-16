"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def build_panini_team_keyboard_from_list(
    teams: list[dict],
) -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_panini_team_keyboard_from_list."""
    rows = []

    for index, team in enumerate(teams):
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{team['flag']} "
                        f"#{team['rank']} "
                        f"{team['display_name']}"
                    ).strip(),
                    callback_data=f"panini_team:{index}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)

