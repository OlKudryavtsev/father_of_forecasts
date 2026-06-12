"""Real implementation extracted from the former bot_runtime monolith."""


from app.formatters.matches import format_match_short_for_group
from app.runtime import ADMIN_NOTIFY_ENABLED, Match, User, bot
from app.services.admin import get_admin_telegram_ids
from app.services.forecast import is_forecast_bot_user

async def notify_group_prediction_saved(
    user: User,
    match: Match,
    is_update: bool = False,
):
    """Handle asynchronous bot workflow for notify_group_prediction_saved."""
    if is_forecast_bot_user(user):
        return
    action_text = "обновил прогноз" if is_update else "сделал прогноз"

    await notify_group_chat(
        "✍️ Прогноз зафиксирован\n\n"
        f"{user.display_name} {action_text} на матч:\n"
        f"{format_match_short_for_group(match)}\n\n"
        "Сам прогноз пока скрыт. "
        "Отец прогнозов уважает тайну до стартового свистка."
    )


async def notify_group_tournament_prediction_saved(
    user: User,
    is_update: bool = False,
):
    """Handle asynchronous bot workflow for notify_group_tournament_prediction_saved."""
    if is_forecast_bot_user(user):
        return

    action_text = "обновил турнирный прогноз" if is_update else "сделал турнирный прогноз"

    await notify_group_chat(
        "🏆 Турнирный прогноз зафиксирован\n\n"
        f"{user.display_name} {action_text} на ЧМ-2026.\n\n"
        "Детали пока не раскрываем. "
        "Пусть интрига живет хотя бы до первого спорного VAR."
    )


async def notify_admins(text: str, exclude_telegram_id: int | None = None):
    """Handle asynchronous bot workflow for notify_admins."""
    if not ADMIN_NOTIFY_ENABLED:
        return

    admin_ids = get_admin_telegram_ids()

    if not admin_ids:
        return

    for admin_telegram_id in admin_ids:
        if exclude_telegram_id and admin_telegram_id == exclude_telegram_id:
            continue

        try:
            await bot.send_message(
                chat_id=admin_telegram_id,
                text=text,
            )
        except Exception as error:
            print(
                f"Failed to send admin notification "
                f"to {admin_telegram_id}: {error}"
            )


async def notify_group_chat(text: str):
    """Handle asynchronous bot workflow for notify_group_chat."""
    from app.services.misc import get_group_chat_id
    group_chat_id = get_group_chat_id()

    if not group_chat_id:
        print("GROUP_CHAT_ID is not set")
        return

    try:
        await bot.send_message(
            chat_id=group_chat_id,
            text=text,
        )
    except Exception as error:
        print(f"Failed to send message to group chat {group_chat_id}: {error}")

    try:
        from app.db import SessionLocal
        from app.services.web_push import notify_active_web_push_subscribers_for_notification

        db = SessionLocal()
        try:
            notify_active_web_push_subscribers_for_notification(
                db,
                notification_key="group_activity",
                title="Отец прогнозов",
                body=text[:220],
                url="/app",
            )
        finally:
            db.close()
    except Exception as error:
        print(f"Failed to send web push notifications: {error}")

