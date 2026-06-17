"""Real implementation extracted from the former bot_runtime monolith."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.runtime import CallbackQuery, Message, SessionLocal, bot
from app.services.admin import get_admin_telegram_ids
from app.services.leagues import approve_user, extract_invite_code_from_start_text, get_league_by_invite_code, reject_user
from app.services.users import get_or_create_user, get_start_message_for_user
from app.handlers.miniapp import answer_with_private_miniapp_button, get_miniapp_url


def _approval_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"access_approve:{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"access_reject:{user_id}"),
            ]
        ]
    )


async def _notify_admins_about_access_request(user, invite_league_name: str | None = None) -> None:
    admin_ids = get_admin_telegram_ids()
    if not admin_ids:
        return

    username_text = f"@{user.username}" if user.username else "без username"
    invite_text = f"\nПриглашение в лигу: {invite_league_name}" if invite_league_name else ""

    text = (
        "🆕 Новая заявка на участие\n\n"
        f"Имя: {user.display_name}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"Username: {username_text}"
        f"{invite_text}\n\n"
        "Подтвердить доступ?"
    )

    for admin_telegram_id in admin_ids:
        if admin_telegram_id == user.telegram_id:
            continue
        try:
            await bot.send_message(
                chat_id=admin_telegram_id,
                text=text,
                reply_markup=_approval_keyboard(user.id),
            )
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

    if message.text and message.text.strip().startswith("/start app"):
        miniapp_url = get_miniapp_url()

        if not miniapp_url:
            await message.answer(
                "Mini App пока не настроен: добавь MINIAPP_URL или PUBLIC_BASE_URL."
            )
            return

        await answer_with_private_miniapp_button(message, miniapp_url)
        return

    invite_code = extract_invite_code_from_start_text(message.text)
    db = SessionLocal()

    try:
        user, created = get_or_create_user(db, message.from_user, invite_code=invite_code)

        invite_league_name = None
        if invite_code:
            invite_league = get_league_by_invite_code(db, invite_code)
            invite_league_name = invite_league.name if invite_league else None

        await message.answer(get_start_message_for_user(user, created))

        if created and getattr(user, "access_status", "approved") == "pending":
            await _notify_admins_about_access_request(user, invite_league_name=invite_league_name)
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
        if not admin_user.is_admin:
            await callback.answer("Недостаточно прав.", show_alert=True)
            return

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
        if not admin_user.is_admin:
            await callback.answer("Недостаточно прав.", show_alert=True)
            return

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
