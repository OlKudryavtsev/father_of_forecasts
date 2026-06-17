"""Real implementation extracted from the former bot_runtime monolith."""

from app.constants.commands import GROUP_ALLOWED_CALLBACK_PREFIXES, GROUP_ALLOWED_COMMANDS
from app.constants.texts import PRIVATE_ONLY_COMMANDS_HINT
from app.runtime import (
    Any,
    Awaitable,
    BaseMiddleware,
    Callable,
    CallbackQuery,
    CommandLog,
    Message,
    SessionLocal,
    TelegramObject,
)
from app.services.admin import extract_command_from_text
from app.services.users import get_or_create_user


PENDING_ALLOWED_COMMANDS = {
    "/start",
    "/help",
    "/rules",
    "/chat_id",
}

PENDING_ALLOWED_CALLBACK_PREFIXES = (
    "access_approve:",
    "access_reject:",
)


class CommandLoggingMiddleware(BaseMiddleware):
    """Defines CommandLoggingMiddleware for the Telegram bot runtime."""
    async def __call__(
            self,
            handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: dict[str, Any],
    ) -> Any:
        """Handle asynchronous bot workflow for __call__."""
        if isinstance(event, Message):
            command = extract_command_from_text(event.text)

            if command:
                db = SessionLocal()

                try:
                    user = None

                    # Do not create a user before /start handler. The /start handler
                    # needs to know whether the user is newly created so it can send
                    # the admin approval request once.
                    if event.from_user and command != "/start":
                        user, _ = get_or_create_user(db, event.from_user)

                    log = CommandLog(
                        user_id=user.id if user else None,
                        telegram_id=event.from_user.id if event.from_user else None,
                        display_name=user.display_name if user else None,
                        command=command,
                        full_text=event.text,
                    )

                    db.add(log)
                    db.commit()

                except Exception as error:
                    db.rollback()
                    print(f"Failed to log command: {error}")

                finally:
                    db.close()

        return await handler(event, data)


class UserAccessStatusMiddleware(BaseMiddleware):
    """Block pending/rejected users from private bot actions before approval."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            command = extract_command_from_text(event.text)
            if not command or event.chat.type != "private" or command in PENDING_ALLOWED_COMMANDS:
                return await handler(event, data)

            db = SessionLocal()
            try:
                user, _ = get_or_create_user(db, event.from_user)
                status = getattr(user, "access_status", "approved") or "approved"
                if status != "approved":
                    await event.answer(_access_status_message(status))
                    return
            finally:
                db.close()

        if isinstance(event, CallbackQuery):
            callback_data = event.data or ""
            if callback_data.startswith(PENDING_ALLOWED_CALLBACK_PREFIXES):
                return await handler(event, data)

            db = SessionLocal()
            try:
                user, _ = get_or_create_user(db, event.from_user)
                status = getattr(user, "access_status", "approved") or "approved"
                if status != "approved":
                    await event.answer(_access_status_message(status), show_alert=True)
                    return
            finally:
                db.close()

        return await handler(event, data)


def _access_status_message(status: str) -> str:
    if status == "pending":
        return "⏳ Заявка на участие еще на рассмотрении. Доступ появится после подтверждения администратора."
    if status == "rejected":
        return "❌ Заявка на участие не одобрена. Если это ошибка, напиши администратору."
    if status == "blocked":
        return "Доступ к турниру закрыт."
    return "Доступ пока не подтвержден."


class GroupCommandAccessMiddleware(BaseMiddleware):
    """Defines GroupCommandAccessMiddleware for the Telegram bot runtime."""
    async def __call__(
        self,
        handler,
        event,
        data,
    ):
        """Handle asynchronous bot workflow for __call__."""
        if isinstance(event, Message):
            command = extract_command_from_text(event.text)

            if command and event.chat.type != "private":
                if command not in GROUP_ALLOWED_COMMANDS:
                    await event.answer(PRIVATE_ONLY_COMMANDS_HINT)
                    return

        return await handler(event, data)


class GroupCallbackAccessMiddleware(BaseMiddleware):
    """Defines GroupCallbackAccessMiddleware for group callback access."""
    async def __call__(
        self,
        handler,
        event,
        data,
    ):
        """Handle asynchronous bot workflow for __call__."""
        if isinstance(event, CallbackQuery):
            message = event.message

            if message and message.chat.type != "private":
                callback_data = event.data or ""

                is_allowed = any(
                    callback_data.startswith(prefix)
                    for prefix in GROUP_ALLOWED_CALLBACK_PREFIXES
                )

                if not is_allowed:
                    await event.answer(
                        "Эта кнопка работает только в личке с ботом.",
                        show_alert=True,
                    )
                    return

        return await handler(event, data)
