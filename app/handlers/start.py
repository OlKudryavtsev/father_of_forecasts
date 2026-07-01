"""Real implementation extracted from the former bot_runtime monolith."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.runtime import CallbackQuery, Message, SessionLocal, bot
from app.services.admin import get_admin_telegram_ids
from app.services.leagues import (
    approve_user,
    can_manage_league,
    extract_invite_code_from_start_text,
    get_league_by_invite_code,
    get_league_member,
    reject_user,
    request_league_join_by_invite_code,
)
from app.services.users import get_or_create_user, get_start_message_for_user
from app.handlers.miniapp import answer_with_private_miniapp_button, get_miniapp_url
from app.handlers.league_quiz import extract_quiz_session_id_from_start_text
from app.keyboards.league_quiz import build_private_quiz_open_keyboard
from app.services.league_quiz import register_for_quiz


def _approval_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"access_approve:{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"access_reject:{user_id}"),
            ]
        ]
    )


async def _notify_admins_about_access_request(db, user, invite_league=None) -> None:
    """Route invited newcomers to the league owner; global admins get an FYI."""
    if invite_league:
        from app.services.league_notifications import notify_league_managers_about_join_request
        await notify_league_managers_about_join_request(db, invite_league, user, access_request=True)
        return

    admin_ids = get_admin_telegram_ids()
    if not admin_ids:
        return
    username_text = f"@{user.username}" if user.username else "без username"
    text = (
        "🆕 Новая заявка на участие\n\n"
        f"Имя: {user.display_name}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"Username: {username_text}\n\n"
        "Подтвердить доступ?"
    )
    for admin_telegram_id in admin_ids:
        if admin_telegram_id == user.telegram_id:
            continue
        try:
            await bot.send_message(chat_id=admin_telegram_id, text=text, reply_markup=_approval_keyboard(user.id))
        except Exception as error:
            print(f"Failed to send access request to admin {admin_telegram_id}: {error}")


async def start_handler(message: Message):
    """Handle asynchronous bot workflow for start_handler."""
    # В группе /start не регистрируем как полноценный личный старт
    if message.chat.type != "private":
        await message.answer(
            "Я тут для развлечений и общей статистики: /fact, /quiz, /archive, /table.\n\n"
            "Прогнозы лучше делать в личке с ботом: /predict"
        )
        return

    quiz_session_id = extract_quiz_session_id_from_start_text(message.text)

    if message.text and message.text.strip().startswith("/start app"):
        miniapp_url = get_miniapp_url()

        if not miniapp_url:
            await message.answer(
                "Mini App пока не настроен: добавь MINIAPP_URL или PUBLIC_BASE_URL."
            )
            return

        await answer_with_private_miniapp_button(message, miniapp_url)
        return

    # A /start quiz_<id> payload is a quiz deep link, never a league invite.
    invite_code = None if quiz_session_id else extract_invite_code_from_start_text(message.text)
    db = SessionLocal()

    try:
        user, created = get_or_create_user(db, message.from_user, invite_code=invite_code)

        invite_league = None
        invite_league_name = None
        if invite_code:
            invite_league = get_league_by_invite_code(db, invite_code)
            invite_league_name = invite_league.name if invite_league else None

        # An already approved user who opened a league deep link sends a
        # membership request; a private league never gains members silently.
        if invite_code and invite_league and getattr(user, "access_status", "approved") == "approved":
            current_member = get_league_member(db, invite_league, user)
            if not current_member or current_member.status != "active":
                _league, member, request_created = request_league_join_by_invite_code(db, user, invite_code)
                if request_created:
                    from app.services.league_notifications import notify_league_managers_about_join_request
                    await notify_league_managers_about_join_request(db, invite_league, user)
                await message.answer(
                    f"⏳ Заявка на вступление в лигу «{invite_league.name}» отправлена ее администратору."
                    if member.status == "pending" else
                    f"Ты уже состоишь в лиге «{invite_league.name}»."
                )
                return

        if quiz_session_id and getattr(user, "access_status", "approved") == "approved":
            try:
                register_for_quiz(db, user, quiz_session_id)
                from app.models import LeagueQuizSession

                quiz_session = db.query(LeagueQuizSession).filter(LeagueQuizSession.id == quiz_session_id).first()
                if quiz_session:
                    await message.answer(
                        f"✅ Вы зарегистрированы на квиз\n\n{quiz_session.title}\n\nЖдём старта игры.",
                        reply_markup=build_private_quiz_open_keyboard(quiz_session.id, get_miniapp_url()),
                    )
                    return
            except (ValueError, PermissionError) as error:
                await message.answer(f"Не удалось зарегистрироваться на квиз: {error}")
                return

        await message.answer(get_start_message_for_user(user, created))

        if created and getattr(user, "access_status", "approved") == "pending":
            await _notify_admins_about_access_request(db, user, invite_league=invite_league)
            return

        if created and getattr(user, "access_status", "approved") == "approved":
            # Администраторы и заранее разрешенные пользователи остаются в прежнем сценарии.
            username_text = (
                f"@{message.from_user.username}"
                if message.from_user.username
                else "без username"
            )

            for admin_telegram_id in get_admin_telegram_ids():
                if admin_telegram_id == user.telegram_id:
                    continue
                try:
                    await bot.send_message(
                        chat_id=admin_telegram_id,
                        text=(
                            "🆕 Новый участник зарегистрировался\n\n"
                            f"Имя: {user.display_name}\n"
                            f"Telegram ID: {user.telegram_id}\n"
                            f"Username: {username_text}"
                        ),
                    )
                except Exception as error:
                    print(f"Failed to send admin registration notification: {error}")

    finally:
        db.close()


async def access_approve_callback(callback: CallbackQuery):
    """Approve a pending user from admin inline button."""
    db = SessionLocal()
    try:
        admin_user, _ = get_or_create_user(db, callback.from_user)

        try:
            user_id = int((callback.data or "").split(":", 1)[1])
        except Exception:
            await callback.answer("Некорректная заявка.", show_alert=True)
            return

        from app.models import User

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await callback.answer("Пользователь не найден.", show_alert=True)
            return

        invite_league = get_league_by_invite_code(db, getattr(user, "pending_invite_code", None))
        if not admin_user.is_admin and not (invite_league and can_manage_league(db, admin_user, invite_league)):
            await callback.answer("Недостаточно прав.", show_alert=True)
            return

        if user.access_status == "approved":
            await callback.answer("Пользователь уже одобрен.")
            return

        joined_leagues = approve_user(db, user, approved_by=admin_user)
        leagues_text = ", ".join(joined_leagues) if joined_leagues else "—"

        await callback.answer("Доступ одобрен.")
        if callback.message:
            try:
                await callback.message.edit_text(
                    "✅ Заявка одобрена\n\n"
                    f"Пользователь: {user.display_name}\n"
                    f"Лиги: {leagues_text}"
                )
            except Exception:
                pass

        approval_text = "✅ Заявка одобрена!\n\n"
        if joined_leagues:
            approval_text += (
                "Ты добавлен в лигу: "
                f"{', '.join(joined_leagues)}.\n\n"
                "Теперь можешь делать прогнозы и смотреть рейтинг своей лиги."
            )
        else:
            approval_text += (
                "Доступ к боту открыт.\n\n"
                "Ты пока не состоишь ни в одной лиге: создай свою лигу в веб-приложении "
                "или вступи в лигу по коду приглашения."
            )

        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=approval_text,
            )
        except Exception as error:
            print(f"Failed to notify approved user {user.telegram_id}: {error}")
    finally:
        db.close()


async def access_reject_callback(callback: CallbackQuery):
    """Reject a pending user from admin inline button."""
    db = SessionLocal()
    try:
        admin_user, _ = get_or_create_user(db, callback.from_user)

        try:
            user_id = int((callback.data or "").split(":", 1)[1])
        except Exception:
            await callback.answer("Некорректная заявка.", show_alert=True)
            return

        from app.models import User

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await callback.answer("Пользователь не найден.", show_alert=True)
            return

        invite_league = get_league_by_invite_code(db, getattr(user, "pending_invite_code", None))
        if not admin_user.is_admin and not (invite_league and can_manage_league(db, admin_user, invite_league)):
            await callback.answer("Недостаточно прав.", show_alert=True)
            return

        if not admin_user.is_admin and invite_league:
            # The owner declines only this league admission. The person remains
            # eligible to receive another invite, rather than being globally banned.
            user.access_status = "approved"
            user.approved_at = user.approved_at or __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            user.pending_invite_code = None
            db.commit()
            await callback.answer("Заявка в лигу отклонена.")
            if callback.message:
                try:
                    await callback.message.edit_text(f"❌ Заявка в лигу «{invite_league.name}» отклонена\n\nПользователь: {user.display_name}")
                except Exception:
                    pass
            try:
                await bot.send_message(chat_id=user.telegram_id, text=f"❌ Заявка в лигу «{invite_league.name}» отклонена ее администратором.")
            except Exception as error:
                print(f"Failed to notify rejected league applicant {user.telegram_id}: {error}")
            return

        reject_user(db, user, rejected_by=admin_user)

        await callback.answer("Заявка отклонена.")
        if callback.message:
            try:
                await callback.message.edit_text(
                    "❌ Заявка отклонена\n\n"
                    f"Пользователь: {user.display_name}"
                )
            except Exception:
                pass

        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    "❌ Заявка на участие отклонена.\n\n"
                    "Если это ошибка, напиши администратору турнира."
                ),
            )
        except Exception as error:
            print(f"Failed to notify rejected user {user.telegram_id}: {error}")
    finally:
        db.close()


async def chat_id_handler(message: Message):
    """Handle asynchronous bot workflow for chat_id_handler."""
    await message.answer(
        f"chat_id: {message.chat.id}\n"
        f"type: {message.chat.type}"
    )


async def league_join_approve_callback(callback: CallbackQuery):
    """Approve a Mini App league join request from Telegram."""
    db = SessionLocal()
    try:
        actor, _ = get_or_create_user(db, callback.from_user)
        try:
            _prefix, league_id_raw, user_id_raw = (callback.data or "").split(":", 2)
            league_id, user_id = int(league_id_raw), int(user_id_raw)
        except Exception:
            await callback.answer("Некорректная заявка.", show_alert=True)
            return
        from app.services.leagues import approve_league_join_request
        member = approve_league_join_request(db, actor, league_id, user_id)
        from app.services.league_notifications import (
            league_manager_telegram_ids,
            notify_global_admins_about_league_event,
            notify_join_decision,
        )
        await notify_join_decision(member.user, member.league, accepted=True)
        await notify_global_admins_about_league_event(
            member.league,
            member.user,
            "member_joined",
            exclude_telegram_ids=league_manager_telegram_ids(db, member.league),
        )
        await callback.answer("Участник добавлен в лигу.")
        if callback.message:
            try:
                await callback.message.edit_text(f"✅ Заявка одобрена\n\nЛига: «{member.league.name}»\nУчастник: {member.user.display_name}")
            except Exception:
                pass
    except (PermissionError, ValueError) as error:
        await callback.answer(str(error), show_alert=True)
    finally:
        db.close()


async def league_join_reject_callback(callback: CallbackQuery):
    """Reject a Mini App league join request from Telegram."""
    db = SessionLocal()
    try:
        actor, _ = get_or_create_user(db, callback.from_user)
        try:
            _prefix, league_id_raw, user_id_raw = (callback.data or "").split(":", 2)
            league_id, user_id = int(league_id_raw), int(user_id_raw)
        except Exception:
            await callback.answer("Некорректная заявка.", show_alert=True)
            return
        from app.services.leagues import reject_league_join_request
        member = reject_league_join_request(db, actor, league_id, user_id)
        from app.services.league_notifications import notify_join_decision
        await notify_join_decision(member.user, member.league, accepted=False)
        await callback.answer("Заявка отклонена.")
        if callback.message:
            try:
                await callback.message.edit_text(f"❌ Заявка отклонена\n\nЛига: «{member.league.name}»\nУчастник: {member.user.display_name}")
            except Exception:
                pass
    except (PermissionError, ValueError) as error:
        await callback.answer(str(error), show_alert=True)
    finally:
        db.close()
