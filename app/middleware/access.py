"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

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

                    if event.from_user:
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
    """Defines GroupCallbackAccessMiddleware for the Telegram bot runtime."""
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

