"""Private Telegram notifications for league ownership workflows."""
from __future__ import annotations
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.models import League, LeagueMember, User
from app.runtime import bot
from app.services.admin import get_admin_telegram_ids

def _manager_users(db, league: League) -> list[User]:
    ids: set[int] = set()
    if league.owner_user_id:
        ids.add(int(league.owner_user_id))
    for member in db.query(LeagueMember).filter(LeagueMember.league_id == league.id, LeagueMember.status == "active", LeagueMember.role.in_(["owner", "admin"])).all():
        ids.add(int(member.user_id))
    return db.query(User).filter(User.id.in_(list(ids))).all() if ids else []


def league_manager_telegram_ids(db, league: League) -> set[int]:
    """Return manager Telegram IDs to avoid duplicate global-admin notices."""
    return {int(manager.telegram_id) for manager in _manager_users(db, league) if manager.telegram_id is not None}

def _join_keyboard(league_id: int, user_id: int, *, access_request: bool) -> InlineKeyboardMarkup:
    """Build callbacks compatible with global-access and league-member flows."""
    if access_request:
        # The global access callbacks resolve the target league from the user's
        # pending invite code and therefore accept exactly one user id.
        approve_callback = f"access_approve:{user_id}"
        reject_callback = f"access_reject:{user_id}"
    else:
        approve_callback = f"league_join_approve:{league_id}:{user_id}"
        reject_callback = f"league_join_reject:{league_id}:{user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=approve_callback),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=reject_callback),
    ]])

async def notify_global_admins_about_league_event(
    league: League,
    actor: User,
    event: str,
    *,
    exclude_telegram_ids: set[int] | None = None,
) -> None:
    labels = {"league_created":"🏁 Создана лига", "join_requested":"⏳ Запрос на вступление в лигу", "member_joined":"👋 Участник вступил в лигу"}
    title = labels.get(event, "ℹ️ Событие лиги")
    username = f"@{actor.username}" if actor.username else "без username"
    text = f"{title}\n\nЛига: «{league.name}»\nУчастник: {actor.display_name}\nUsername: {username}\nTelegram ID: {actor.telegram_id}"
    excluded = {int(value) for value in (exclude_telegram_ids or set())}
    for admin_id in get_admin_telegram_ids():
        if int(admin_id) == int(actor.telegram_id) or int(admin_id) in excluded:
            continue
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception as error:
            print(f"Failed to send league event to global admin {admin_id}: {error}")

async def notify_league_managers_about_join_request(db, league: League, user: User, *, access_request: bool = False) -> None:
    username = f"@{user.username}" if user.username else "без username"
    kind = "Заявка на участие через приглашение" if access_request else "Заявка на вступление в лигу"
    text = f"👋 {kind}\n\nЛига: «{league.name}»\nУчастник: {user.display_name}\nUsername: {username}\n\nОдобрить вступление?"
    manager_ids = league_manager_telegram_ids(db, league)
    for manager in _manager_users(db, league):
        if manager.telegram_id == user.telegram_id:
            continue
        try:
            await bot.send_message(chat_id=manager.telegram_id, text=text, reply_markup=_join_keyboard(league.id, user.id, access_request=access_request))
        except Exception as error:
            print(f"Failed to notify league manager {manager.telegram_id}: {error}")
    # A global administrator who is also the league manager already received the
    # actionable request above, so do not additionally send an FYI duplicate.
    await notify_global_admins_about_league_event(league, user, "join_requested", exclude_telegram_ids=manager_ids)

async def notify_join_decision(user: User, league: League, accepted: bool) -> None:
    text = f"✅ Тебя приняли в лигу «{league.name}». Теперь она доступна в приложении и рейтинге." if accepted else f"❌ Заявка в лигу «{league.name}» отклонена ее администратором."
    try:
        await bot.send_message(chat_id=user.telegram_id, text=text)
    except Exception as error:
        print(f"Failed to notify user {user.telegram_id} about league decision: {error}")
