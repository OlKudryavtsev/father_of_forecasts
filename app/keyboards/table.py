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
