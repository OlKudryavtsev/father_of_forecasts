"""Real implementation extracted from the former bot_runtime monolith."""


from app.runtime import InlineKeyboardButton, InlineKeyboardMarkup

def build_category_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """
    prefix:
    - fact_category
    - quiz_category
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎲 Любая категория",
                    callback_data=f"{prefix}:any",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 ЧМ-2026",
                    callback_data=f"{prefix}:wc2026",
                ),
                InlineKeyboardButton(
                    text="📜 История",
                    callback_data=f"{prefix}:history",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Рекорды",
                    callback_data=f"{prefix}:record",
                ),
                InlineKeyboardButton(
                    text="👥 Сборные",
                    callback_data=f"{prefix}:team",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Игроки",
                    callback_data=f"{prefix}:player",
                ),
                InlineKeyboardButton(
                    text="🏟 Хозяева",
                    callback_data=f"{prefix}:host",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏆 Трофеи",
                    callback_data=f"{prefix}:trophy",
                ),
                InlineKeyboardButton(
                    text="😂 Курьезы",
                    callback_data=f"{prefix}:funny",
                ),
            ],
        ]
    )

