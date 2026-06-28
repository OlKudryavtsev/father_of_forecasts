"""Telegram and Web/PWA notification helpers."""

from __future__ import annotations

from app.constants.notifications import ADMIN_SETTING_BY_NOTIFICATION_KEY, NOTIFICATION_DEFAULTS
from app.formatters.matches import format_match_short_for_group
from app.models import AppSetting, League, User, UserNotificationSetting
from app.runtime import ADMIN_NOTIFY_ENABLED, Match, bot
from app.services.admin import get_admin_telegram_ids
from app.services.forecast import is_forecast_bot_user


def _global_notification_enabled(db, notification_key: str) -> bool:
    setting_key = ADMIN_SETTING_BY_NOTIFICATION_KEY.get(notification_key)
    if not setting_key:
        return True
    setting = db.query(AppSetting).filter(AppSetting.setting_key == setting_key).first()
    if not setting:
        return True
    return str(setting.setting_value).lower() == "true"


def _user_notification_enabled(db, user_id: int, notification_key: str) -> bool:
    default = NOTIFICATION_DEFAULTS.get(notification_key, True)
    setting = (
        db.query(UserNotificationSetting)
        .filter(
            UserNotificationSetting.user_id == user_id,
            UserNotificationSetting.notification_key == notification_key,
        )
        .first()
    )
    if not setting:
        return default
    return bool(setting.is_enabled)


def _approved_users_query(db):
    return db.query(User).filter(User.access_status == "approved").order_by(User.display_name.asc())


async def notify_private_users(
    db,
    notification_key: str,
    title: str,
    text: str,
    url: str = "/app",
    reply_markup=None,
    exclude_user_id: int | None = None,
) -> int:
    """Send a Telegram DM + optional Web Push to approved users that enabled a notification type."""
    if not _global_notification_enabled(db, notification_key):
        return 0

    users = _approved_users_query(db).all()
    sent = 0

    for user in users:
        if exclude_user_id and user.id == exclude_user_id:
            continue
        if is_forecast_bot_user(user):
            continue
        if not _user_notification_enabled(db, user.id, notification_key):
            continue

        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                reply_markup=reply_markup,
            )
            sent += 1
        except Exception as error:
            print(f"Failed to send private Telegram notification to {user.telegram_id}: {error}")

        try:
            from app.services.web_push import notify_web_push_subscribers_for_user_if_enabled

            notify_web_push_subscribers_for_user_if_enabled(
                db,
                user_id=user.id,
                notification_key=notification_key,
                title=title,
                body=text[:220],
                url=url,
            )
        except Exception as push_error:
            print(f"Failed to send private web push to {user.telegram_id}: {push_error}")

    return sent


async def notify_private_user(
    db,
    user: User,
    notification_key: str,
    title: str,
    text: str,
    url: str = "/app",
    reply_markup=None,
) -> bool:
    """Send one Telegram DM + optional Web Push if enabled."""
    if user.access_status != "approved" or is_forecast_bot_user(user):
        return False
    if not _global_notification_enabled(db, notification_key):
        return False
    if not _user_notification_enabled(db, user.id, notification_key):
        return False

    ok = False
    try:
        await bot.send_message(chat_id=user.telegram_id, text=text, reply_markup=reply_markup)
        ok = True
    except Exception as error:
        print(f"Failed to send private Telegram notification to {user.telegram_id}: {error}")

    try:
        from app.services.web_push import notify_web_push_subscribers_for_user_if_enabled

        notify_web_push_subscribers_for_user_if_enabled(
            db,
            user_id=user.id,
            notification_key=notification_key,
            title=title,
            body=text[:220],
            url=url,
        )
    except Exception as push_error:
        print(f"Failed to send private web push to {user.telegram_id}: {push_error}")

    return ok


async def notify_league_chat(league: League, text: str) -> bool:
    raw_chat_id = getattr(league, "chat_id", None)
    chat_id = str(raw_chat_id or "").strip()
    if not chat_id:
        return False
    try:
        await bot.send_message(chat_id=int(chat_id), text=text)
        return True
    except ValueError:
        print(f"Invalid chat_id for league {league.id}: {chat_id}")
        return False
    except Exception as error:
        print(f"Failed to send message to league chat {chat_id}: {error}")
        return False


def _is_default_league_member(user: User) -> bool:
    """Keep old GROUP_CHAT_ID activity only for members of «Отец прогнозов»."""
    try:
        from app.db import SessionLocal
        from app.models import User as DbUser
        from app.services.leagues import is_user_in_default_league

        db = SessionLocal()
        try:
            db_user = db.query(DbUser).filter(DbUser.id == user.id).first()
            return bool(db_user and is_user_in_default_league(db, db_user))
        finally:
            db.close()
    except Exception as error:
        print(f"Failed to check default league membership for group notification: {error}")
        return False


async def _notify_default_group_chat_if_default_member(db, user: User, text: str) -> set[str]:
    """Send a legacy default-group notification and return its chat id for dedupe."""
    if not _is_default_league_member(user):
        return set()

    from app.services.misc import get_group_chat_id

    group_chat_id = get_group_chat_id()
    if not group_chat_id:
        return set()

    await notify_group_chat(text)
    return {str(group_chat_id)}


async def _notify_actor_league_chats(
    db,
    user: User,
    text: str,
    skip_chat_ids: set[str] | None = None,
) -> set[str]:
    """Notify every relevant league chat once, even with duplicate chat ids."""
    sent_chat_ids = set(skip_chat_ids or set())
    try:
        from app.services.leagues import get_user_active_leagues_with_chat, normalize_telegram_chat_id

        for league in get_user_active_leagues_with_chat(db, user):
            chat_id = normalize_telegram_chat_id(getattr(league, "chat_id", None))
            if not chat_id or chat_id in sent_chat_ids:
                continue
            if await notify_league_chat(league, text):
                sent_chat_ids.add(chat_id)
    except Exception as error:
        print(f"Failed to send actor league chat notifications: {error}")
    return sent_chat_ids


async def notify_group_prediction_saved(
    user: User,
    match: Match,
    is_update: bool = False,
):
    """Notify personal users and relevant league/group chats about saved match prediction."""
    if is_forecast_bot_user(user):
        return

    action_text = "обновил прогноз" if is_update else "сделал прогноз"
    text = (
        "✍️ Прогноз зафиксирован\n\n"
        f"{user.display_name} {action_text} на матч:\n"
        f"{format_match_short_for_group(match)}\n\n"
        "Сам прогноз пока скрыт. "
        "Отец прогнозов уважает тайну до стартового свистка."
    )

    from app.db import SessionLocal
    from app.models import User as DbUser

    db = SessionLocal()
    try:
        db_user = db.query(DbUser).filter(DbUser.id == user.id).first() or user
        await notify_private_users(
            db,
            notification_key="group_activity",
            title="Отец прогнозов",
            text=text,
            exclude_user_id=user.id,
        )
        sent_chat_ids = await _notify_default_group_chat_if_default_member(db, db_user, text)
        await _notify_actor_league_chats(db, db_user, text, skip_chat_ids=sent_chat_ids)
    finally:
        db.close()


async def notify_group_tournament_prediction_saved(
    user: User,
    is_update: bool = False,
):
    """Notify personal users and relevant league/group chats about tournament prediction."""
    if is_forecast_bot_user(user):
        return

    action_text = "обновил турнирный прогноз" if is_update else "сделал турнирный прогноз"
    text = (
        "🏆 Турнирный прогноз зафиксирован\n\n"
        f"{user.display_name} {action_text} на ЧМ-2026.\n\n"
        "Детали пока не раскрываем. "
        "Пусть интрига живет хотя бы до первого спорного VAR."
    )

    from app.db import SessionLocal
    from app.models import User as DbUser

    db = SessionLocal()
    try:
        db_user = db.query(DbUser).filter(DbUser.id == user.id).first() or user
        await notify_private_users(
            db,
            notification_key="group_activity",
            title="Отец прогнозов",
            text=text,
            exclude_user_id=user.id,
        )
        sent_chat_ids = await _notify_default_group_chat_if_default_member(db, db_user, text)
        await _notify_actor_league_chats(db, db_user, text, skip_chat_ids=sent_chat_ids)
    finally:
        db.close()


async def notify_admins(text: str, exclude_telegram_id: int | None = None):
    """Send personal admin notifications only; never to GROUP_CHAT_ID."""
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
    """Send to legacy GROUP_CHAT_ID only. Use only for «Отец прогнозов» league events."""
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
