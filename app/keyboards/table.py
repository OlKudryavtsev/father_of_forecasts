"""League-aware Telegram table keyboards."""

from app.formatters.table import shorten_table_name
from app.runtime import InlineKeyboardButton, InlineKeyboardMarkup

def build_table_buttons_keyboard(rows: list[dict]) -> InlineKeyboardMarkup:
    keyboard = [[
        InlineKeyboardButton(text="№", callback_data="table_noop"),
        InlineKeyboardButton(text="Игрок", callback_data="table_noop"),
        InlineKeyboardButton(text="О", callback_data="table_noop"),
        InlineKeyboardButton(text="🎯", callback_data="table_noop"),
        InlineKeyboardButton(text="✅", callback_data="table_noop"),
        InlineKeyboardButton(text="🏆", callback_data="table_noop"),
    ]]
    for index, row in enumerate(rows, start=1):
        keyboard.append([
            InlineKeyboardButton(text=str(index), callback_data="table_noop"),
            InlineKeyboardButton(text=shorten_table_name(row["name"]), callback_data="table_noop"),
            InlineKeyboardButton(text=str(row["points"]), callback_data="table_noop"),
            InlineKeyboardButton(text=str(row["exact_scores"]), callback_data="table_noop"),
            InlineKeyboardButton(text=str(row["outcomes"]), callback_data="table_noop"),
            InlineKeyboardButton(text=str(row["tournament_points"]), callback_data="table_noop"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_league_selector_keyboard(leagues) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🏆 {league.name}", callback_data=f"table_league:{league.id}")]
        for league in leagues
    ])


def build_standings_selector_keyboard(rows: list[dict], league_id: int) -> InlineKeyboardMarkup:
    """Choose a league member whose championship scenarios should be posted."""
    keyboard = []
    for row in rows:
        user_id = int(row.get("user_id") or 0)
        if not user_id:
            continue
        title = shorten_table_name(str(row.get("name") or "Участник"), max_len=28)
        points = int(row.get("points") or 0)
        keyboard.append([
            InlineKeyboardButton(
                text=f"{title} · {points} очк.",
                callback_data=f"standings_pick:{league_id}:{user_id}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
