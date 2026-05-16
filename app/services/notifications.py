"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

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

