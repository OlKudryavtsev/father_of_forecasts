"""Real implementation extracted from the former bot_runtime monolith."""


from app.runtime import Message, SessionLocal
from app.services.notifications import notify_admins, notify_group_chat
from app.services.users import get_or_create_user, get_start_message_for_user

async def start_handler(message: Message):
    """Handle asynchronous bot workflow for start_handler."""
    # В группе /start не регистрируем как полноценный личный старт
    if message.chat.type != "private":
        await message.answer(
            "Я тут для развлечений и общей статистики: /fact, /quiz, /archive, /table.\n\n"
            "Прогнозы лучше делать в личке с ботом: /predict"
        )
        return

    db = SessionLocal()

    try:
        user, created = get_or_create_user(db, message.from_user)

        await message.answer(
            get_start_message_for_user(user, created)
        )

        if created:
            username_text = (
                f"@{message.from_user.username}"
                if message.from_user.username
                else "без username"
            )

            # Старое уведомление админам, если оно есть
            await notify_admins(
                "🆕 Новый участник зарегистрировался\n\n"
                f"Имя: {user.display_name}\n"
                f"Telegram ID: {user.telegram_id}\n"
                f"Username: {username_text}",
                exclude_telegram_id=user.telegram_id,
            )

            # Новое уведомление в общий чат
            await notify_group_chat(
                "🆕 Новый участник зашел в турнир\n\n"
                f"{user.display_name} зарегистрировался в «Отце прогнозов».\n\n"
                "Отец прогнозов одобрительно открыл Excel, хотя Excel уже не нужен."
            )

    finally:
        db.close()


async def chat_id_handler(message: Message):
    """Handle asynchronous bot workflow for chat_id_handler."""
    await message.answer(
        f"chat_id: {message.chat.id}\n"
        f"type: {message.chat.type}"
    )

