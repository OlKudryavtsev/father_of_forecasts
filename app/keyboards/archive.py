"""Real implementation extracted from the former bot_runtime monolith."""


from app.runtime import InlineKeyboardButton, InlineKeyboardMarkup

def build_archive_keyboard() -> InlineKeyboardMarkup:
    """Provide bot helper logic for build_archive_keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎲 Любая карточка",
                    callback_data="archive_category:any",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇶🇦 ЧМ-2022",
                    callback_data="archive_category:wc2022",
                ),
                InlineKeyboardButton(
                    text="🇩🇪 ЧЕ-2024",
                    callback_data="archive_category:euro2024",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🤦 Коллективные нули",
                    callback_data="archive_category:collective_fail",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Коллективные попадания",
                    callback_data="archive_category:collective_success",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎭 Долгосрок-драма",
                    callback_data="archive_category:longterm_drama",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏅 Достижения",
                    callback_data="archive_category:achievement",
                ),
                InlineKeyboardButton(
                    text="⚔️ Дерби",
                    callback_data="archive_category:rivalry",
                ),
            ],
        ]
    )

