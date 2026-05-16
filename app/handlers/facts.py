"""Real implementation extracted from the former bot_runtime monolith."""


from app.constants.categories import FACT_QUIZ_CATEGORIES
from app.formatters.facts import format_world_cup_fact
from app.keyboards.facts import build_category_keyboard
from app.runtime import (
    CallbackQuery,
    FactDeliveryLog,
    Message,
    SessionLocal,
    WorldCupFact,
    random,
)
from app.services.facts import send_fact_by_category
from app.services.users import get_or_create_user

async def fact_handler(message: Message):
    """Handle asynchronous bot workflow for fact_handler."""
    db = SessionLocal()

    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) == 1:
            await message.answer(
                "📚 Выбери категорию факта:",
                reply_markup=build_category_keyboard("fact_category"),
            )
            return

        category = parts[1].strip().lower()

        if category == "any":
            category = None

        await send_fact_by_category(
            message=message,
            db=db,
            category=category,
            delivery_type="manual",
        )

    finally:
        db.close()


async def fact_category_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for fact_category_callback."""
    db = SessionLocal()

    try:
        category = callback.data.split(":")[1]

        if category == "any":
            category = None

        query = db.query(WorldCupFact).filter(
            WorldCupFact.is_active == True,
            WorldCupFact.needs_verification == False,
        )

        if category:
            query = query.filter(WorldCupFact.category == category)

        facts = query.all()

        if not facts:
            await callback.message.answer(
                "Фактов по такой категории пока нет.\n\n"
                "Попробуй другую категорию: /fact"
            )
            await callback.answer()
            return

        fact = random.choice(facts)

        user, _ = get_or_create_user(db, callback.from_user)

        db.add(
            FactDeliveryLog(
                fact_id=fact.id,
                user_id=user.id,
                telegram_id=user.telegram_id,
                delivery_type="manual",
            )
        )
        db.commit()

        category_text = FACT_QUIZ_CATEGORIES.get(
            category or "any",
            "🎲 Любая категория",
        )

        await callback.message.answer(
            f"{category_text}\n\n"
            f"{format_world_cup_fact(fact)}"
        )

        await callback.answer()

    finally:
        db.close()

