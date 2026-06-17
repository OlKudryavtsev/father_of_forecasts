"""Real implementation extracted from the former bot_runtime monolith."""

from datetime import datetime, timezone

from app.constants.texts import DEFAULT_FIRST_START_MESSAGE, DEFAULT_REPEAT_START_MESSAGES, FIRST_START_MESSAGES_BY_TELEGRAM_ID, REPEAT_START_MESSAGES_BY_TELEGRAM_ID
from app.runtime import Message, User, is_admin_telegram_id, random


def is_group_chat(message: Message) -> bool:
    """Provide bot helper logic for is_group_chat."""
    return message.chat.type in {"group", "supergroup"}


def _normalize_invite_code(invite_code: str | None) -> str | None:
    code = (invite_code or "").strip()
    if not code:
        return None
    if code.startswith("league_"):
        code = code.removeprefix("league_").strip()
    if code.startswith("invite_"):
        code = code.removeprefix("invite_").strip()
    return code or None


def get_or_create_user(db, telegram_user, invite_code: str | None = None):
    """Create/update local user.

    Stage 2 of league support makes new non-admin users pending until an admin
    approves them. Existing users keep their current access_status.
    """
    admin_status = is_admin_telegram_id(telegram_user.id)
    normalized_invite_code = _normalize_invite_code(invite_code)

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

        if admin_status and getattr(existing_user, "access_status", "approved") != "approved":
            existing_user.access_status = "approved"
            existing_user.approved_at = existing_user.approved_at or datetime.now(timezone.utc)
            changed = True

        if normalized_invite_code and getattr(existing_user, "access_status", "approved") != "approved":
            if getattr(existing_user, "pending_invite_code", None) != normalized_invite_code:
                existing_user.pending_invite_code = normalized_invite_code
                changed = True

        if changed:
            db.commit()
            db.refresh(existing_user)

        return existing_user, False

    now = datetime.now(timezone.utc)
    access_status = "approved" if admin_status else "pending"

    new_user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        display_name=telegram_user.full_name,
        is_admin=admin_status,
        access_status=access_status,
        approved_at=now if access_status == "approved" else None,
        pending_invite_code=normalized_invite_code,
        access_requested_at=now,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user, True


def get_start_message_for_user(user: User, created: bool) -> str:
    """Return start message based on access status."""
    access_status = getattr(user, "access_status", "approved") or "approved"

    if access_status == "pending":
        if created:
            return (
                "👋 Привет! Заявка на участие отправлена администратору.\n\n"
                "После подтверждения ты сможешь делать прогнозы, смотреть рейтинг "
                "и пользоваться веб-приложением."
            )
        return (
            "⏳ Твоя заявка уже на рассмотрении.\n\n"
            "Когда администратор подтвердит доступ, я напишу тебе."
        )

    if access_status == "rejected":
        return (
            "Заявка на участие пока не одобрена.\n\n"
            "Если это ошибка, напиши администратору турнира."
        )

    if access_status == "blocked":
        return "Доступ к турниру закрыт."

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
