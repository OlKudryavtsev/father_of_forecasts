"""Real implementation extracted from the former bot_runtime monolith."""


from app.formatters.archive import format_archive_card
from app.runtime import HistoricalArchiveCard, HistoricalArchiveDeliveryLog, Message, SessionLocal, random
from app.services.users import get_or_create_user

async def archive_handler(message: Message):
    """Handle asynchronous bot workflow for archive_handler."""
    db = SessionLocal()

    try:
        parts = message.text.split(maxsplit=1)
        filter_value = parts[1].strip().lower() if len(parts) > 1 else None

        query = db.query(HistoricalArchiveCard).filter(
            HistoricalArchiveCard.is_active == True,
            HistoricalArchiveCard.is_public == True,
        )

        if filter_value:
            # Можно фильтровать по турниру или типу:
            # /archive wc2022
            # /archive euro2024
            # /archive collective_fail
            query = query.filter(
                (HistoricalArchiveCard.tournament_code == filter_value)
                | (HistoricalArchiveCard.card_type == filter_value)
            )

        cards = query.all()

        if not cards:
            await message.answer(
                "Архивных карточек по такому фильтру пока нет.\n\n"
                "Попробуй просто /archive"
            )
            return

        card = random.choice(cards)

        user, _ = get_or_create_user(db, message.from_user)

        db.add(
            HistoricalArchiveDeliveryLog(
                archive_card_id=card.id,
                user_id=user.id,
                telegram_id=user.telegram_id,
                chat_id=message.chat.id,
                delivery_type="manual",
            )
        )
        db.commit()

        await message.answer(format_archive_card(card))

    finally:
        db.close()

