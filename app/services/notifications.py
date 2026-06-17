"""Telegram and Web Push notification helpers."""

from __future__ import annotations

from app.constants.notifications import ADMIN_SETTING_BY_NOTIFICATION_KEY, NOTIFICATION_DEFAULTS
from app.formatters.matches import format_match_short_for_group
from app.runtime import ADMIN_NOTIFY_ENABLED, Match, User, bot
from app.services.admin import get_admin_telegram_ids
from app.services.forecast import is_forecast_bot_user


def _safe_rollback(db) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _global_notification_enabled(db, notification_key: str) -> bool:
    """Return global admin switch for Telegram/Web notifications."""
    try:
        from app.models import AppSetting

        setting_key = ADMIN_SETTING_BY_NOTIFICATION_KEY.get(notification_key)
        if not setting_key:
            return True
        setting = db.query(AppSetting).filter(AppSetting.setting_key == setting_key).first()
        if setting is None:
            return True
        return str(setting.setting_value).lower() == "true"
    except Exception:
        _safe_rollback(db)
        return True


def _user_notification_enabled(db, user_id: int, notification_key: str) -> bool:
    """Return whether a user enabled a notification type; defaults to enabled."""
    try:
        from app.models import UserNotificationSetting

        default = NOTIFICATION_DEFAULTS.get(notification_key, True)
        setting = (
            db.query(UserNotificationSetting)
            .filter(
                UserNotificationSetting.user_id == user_id,
                UserNotificationSetting.notification_key == notification_key,
            )
            .first()
        )
        return default if setting is None else bool(setting.is_enabled)
    except Exception:
        _safe_rollback(db)
        return NOTIFICATION_DEFAULTS.get(notification_key, True)


def get_personal_notification_users(db, notification_key: str | None = None, league_id: int | None = None) -> list[User]:
    """Return approved users who should receive a private bot notification.

    If league_id is provided, users are limited to active members of that league.
    Notification settings are respected when a notification_key is provided.
    """
    try:
        from app.models import LeagueMember

        query = db.query(User).filter(User.access_status == "approved")
        if league_id is not None:
            query = query.join(LeagueMember, LeagueMember.user_id == User.id).filter(
                LeagueMember.league_id == league_id,
                LeagueMember.status == "active",
            )
        users = query.order_by(User.display_name.asc()).all()
    except Exception:
        _safe_rollback(db)
        users = db.query(User).order_by(User.display_name.asc()).all()

    if notification_key is None:
        return users
    if not _global_notification_enabled(db, notification_key):
        return []
    return [user for user in users if _user_notification_enabled(db, user.id, notification_key)]


async def send_private_notifications(
    db,
    *,
    notification_key: str,
    title: str,
    text: str,
    users: list[User] | None = None,
    reply_markup=None,
    url: str = "/app",
) -> int:
    """Send Telegram private notifications and matching Web Push to users."""
    if not _global_notification_enabled(db, notification_key):
        return 0

    if users is None:
        users = get_personal_notification_users(db, notification_key=notification_key)
    else:
        users = [user for user in users if _user_notification_enabled(db, user.id, notification_key)]

    sent = 0
    for user in users:
        if not getattr(user, "telegram_id", None):
            continue
        try:
            await bot.send_message(chat_id=user.telegram_id, text=text, reply_markup=reply_markup)
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
            print(f"Failed to send private Web Push to {user.telegram_id}: {push_error}")

    return sent


def _is_default_league_member_db(db, user: User) -> bool:
    """Keep old GROUP_CHAT_ID activity only for members of «Отец прогнозов»."""
    try:
        from app.services.leagues import is_user_in_default_league

        return bool(is_user_in_default_league(db, user))
    except Exception as error:
        print(f"Failed to check default league membership for group notification: {error}")
        return False


def _is_default_league_member(user: User) -> bool:
    try:
        from app.db import SessionLocal
        from app.models import User as DbUser

        db = SessionLocal()
        try:
            db_user = db.query(DbUser).filter(DbUser.id == user.id).first()
            return bool(db_user and _is_default_league_member_db(db, db_user))
        finally:
            db.close()
    except Exception as error:
        print(f"Failed to check default league membership for group notification: {error}")
        return False


async def notify_telegram_chat(chat_id: int | str | None, text: str) -> bool:
    """Send a message to a Telegram chat id."""
    if not chat_id:
        return False
    try:
        await bot.send_message(chat_id=int(chat_id), text=text)
        return True
    except Exception as error:
        print(f"Failed to send message to chat {chat_id}: {error}")
        return False


async def notify_group_chat(text: str):
    """Legacy GROUP_CHAT_ID delivery only, without broad Web Push fan-out."""
    from app.services.misc import get_group_chat_id

    group_chat_id = get_group_chat_id()
    if not group_chat_id:
        print("GROUP_CHAT_ID is not set")
        return
    await notify_telegram_chat(group_chat_id, text)


def get_user_active_leagues_for_notifications(db, user: User):
    """Return active leagues for a user."""
    try:
        from app.models import League, LeagueMember

        return (
            db.query(League)
            .join(LeagueMember, LeagueMember.league_id == League.id)
            .filter(
                LeagueMember.user_id == user.id,
                LeagueMember.status == "active",
                League.is_active == True,
            )
            .all()
        )
    except Exception:
        _safe_rollback(db)
        return []


def get_leagues_with_chat_id(db):
    """Return active leagues that have a Telegram chat_id configured."""
    try:
        from app.models import League

        return (
            db.query(League)
            .filter(
                League.is_active == True,
                League.chat_id.isnot(None),
            )
            .all()
        )
    except Exception:
        _safe_rollback(db)
        return []


async def notify_league_chats_for_user_activity(db, user: User, text: str) -> int:
    """Notify all league chats where the actor is an active member.

    GROUP_CHAT_ID is treated as the legacy chat for the system league only.
    Private league chats use leagues.chat_id.
    """
    sent = 0
    leagues = get_user_active_leagues_for_notifications(db, user)
    for league in leagues:
        if getattr(league, "chat_id", None):
            if await notify_telegram_chat(league.chat_id, text):
                sent += 1

    if _is_default_league_member_db(db, user):
        from app.services.misc import get_group_chat_id

        if await notify_telegram_chat(get_group_chat_id(), text):
            sent += 1

    return sent


async def notify_group_prediction_saved(
    user: User,
    match: Match,
    is_update: bool = False,
):
    """Notify relevant league chats when a participant makes/updates a match forecast."""
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

    try:
        from app.db import SessionLocal

        db = SessionLocal()
        try:
            await notify_league_chats_for_user_activity(db, user, text)
            # Личные уведомления об активности получают участники тех же лиг.
            notified_user_ids = set()
            for league in get_user_active_leagues_for_notifications(db, user):
                recipients = get_personal_notification_users(db, notification_key="group_activity", league_id=league.id)
                recipients = [recipient for recipient in recipients if recipient.id not in notified_user_ids and recipient.id != user.id]
                for recipient in recipients:
                    notified_user_ids.add(recipient.id)
                await send_private_notifications(
                    db,
                    notification_key="group_activity",
                    title="Отец прогнозов",
                    text=text,
                    users=recipients,
                    url="/app",
                )
        finally:
            db.close()
    except Exception as error:
        print(f"Failed to send league prediction notifications: {error}")


async def notify_group_tournament_prediction_saved(
    user: User,
    is_update: bool = False,
):
    """Notify relevant league chats about tournament prediction activity."""
    if is_forecast_bot_user(user):
        return

    action_text = "обновил турнирный прогноз" if is_update else "сделал турнирный прогноз"
    text = (
        "🏆 Турнирный прогноз зафиксирован\n\n"
        f"{user.display_name} {action_text} на ЧМ-2026.\n\n"
        "Детали пока не раскрываем. "
        "Пусть интрига живет хотя бы до первого спорного VAR."
    )

    try:
        from app.db import SessionLocal

        db = SessionLocal()
        try:
            await notify_league_chats_for_user_activity(db, user, text)
            notified_user_ids = set()
            for league in get_user_active_leagues_for_notifications(db, user):
                recipients = get_personal_notification_users(db, notification_key="group_activity", league_id=league.id)
                recipients = [recipient for recipient in recipients if recipient.id not in notified_user_ids and recipient.id != user.id]
                for recipient in recipients:
                    notified_user_ids.add(recipient.id)
                await send_private_notifications(
                    db,
                    notification_key="group_activity",
                    title="Отец прогнозов",
                    text=text,
                    users=recipients,
                    url="/app",
                )
        finally:
            db.close()
    except Exception as error:
        print(f"Failed to send league tournament prediction notifications: {error}")


async def notify_admins(text: str, exclude_telegram_id: int | None = None):
    """Send private admin notifications only."""
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
