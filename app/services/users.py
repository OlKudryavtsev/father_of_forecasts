"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def is_group_chat(message: Message) -> bool:
    """Provide bot helper logic for is_group_chat."""
    return message.chat.type in {"group", "supergroup"}


def get_or_create_user(db, telegram_user):
    """Provide bot helper logic for get_or_create_user."""
    admin_status = is_admin_telegram_id(telegram_user.id)

    existing_user = db.query(User).filter(
        User.telegram_id == telegram_user.id
    ).first()

    if existing_user:
        changed = False

        if existing_user.username != telegram_user.username:
            existing_user.username = telegram_user.username
            changed = True

        if existing_user.display_name != telegram_user.full_name:
            existing_user.display_name = telegram_user.full_name
            changed = True

        if existing_user.is_admin != admin_status:
            existing_user.is_admin = admin_status
            changed = True

        if changed:
            db.commit()
            db.refresh(existing_user)

        return existing_user, False

    new_user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        display_name=telegram_user.full_name,
        is_admin=admin_status,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user, True


def get_start_message_for_user(user: User, created: bool) -> str:
    """Provide bot helper logic for get_start_message_for_user."""
    if created:
        return FIRST_START_MESSAGES_BY_TELEGRAM_ID.get(
            user.telegram_id,
            DEFAULT_FIRST_START_MESSAGE,
        )

    repeat_messages = REPEAT_START_MESSAGES_BY_TELEGRAM_ID.get(
        user.telegram_id,
        DEFAULT_REPEAT_START_MESSAGES,
    )

    return random.choice(repeat_messages)

