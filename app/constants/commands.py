"""Command allowlists and callback allowlists."""

from app.constants.texts import PRIVATE_ONLY_COMMANDS_HINT

GROUP_ALLOWED_COMMANDS = {
    "/start",
    "/help",
    "/rules",
    "/fact",
    "/quiz",
    "/quiz_finish",
    "/quiz_table",
    "/archive",
    "/chat_id",
    "/panini",

    # Добавляем:
    "/matches_all",
    "/forecast",
    "/match",
    "/table",
    "/table_buttons",
    "/predictions",
    "/tournament_predictions",
}

GROUP_ALLOWED_CALLBACK_PREFIXES = {
    "fact_category:",
    "quiz_category:",
    "group_quiz_answer:",
    "archive_category:",

    # Добавляем:
    "forecast_match:",
    "panini_team:",
    "table_noop",
}
