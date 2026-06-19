"""Real implementation extracted from the former bot_runtime monolith."""


from app.formatters.matches import format_match_label
from app.runtime import InlineKeyboardButton, InlineKeyboardMarkup, Match

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



def build_prediction_reminder_keyboard(match: Match, has_prediction: bool) -> InlineKeyboardMarkup:
    """Build one clear action for the personal pre-match reminder."""
    label = "✏️ Изменить прогноз" if has_prediction else "📝 Сделать прогноз"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"predict_match:{match.id}")]
        ]
    )
