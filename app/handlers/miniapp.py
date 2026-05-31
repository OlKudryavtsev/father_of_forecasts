"""Handlers for opening the Telegram Mini App portal."""

import os

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.runtime import Message, bot


def get_miniapp_url() -> str | None:
    """Return public Mini App URL configured for Telegram WebApp buttons."""
    explicit_url = os.getenv("MINIAPP_URL", "").strip()

    if explicit_url:
        return explicit_url

    public_base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")

    if public_base_url:
        return f"{public_base_url}/app"

    railway_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()

    if railway_url:
        return f"https://{railway_url}/app"

    return None


def build_private_miniapp_keyboard(miniapp_url: str) -> InlineKeyboardMarkup:
    """Build WebApp keyboard for private chats.

    Telegram allows inline buttons with ``web_app=WebAppInfo(...)`` only in
    private chats. Sending the same button to a group causes
    ``Bad Request: BUTTON_TYPE_INVALID``.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть турнирный портал",
                    web_app=WebAppInfo(url=miniapp_url),
                )
            ]
        ]
    )


def build_group_miniapp_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Build URL keyboard for group chats.

    In group chats we cannot send a WebApp button directly. Instead, we send a
    regular deep link to the private chat with the bot. The private ``/start app``
    handler will then show the proper WebApp button.
    """
    username = bot_username.lstrip("@").strip()

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть в боте",
                    url=f"https://t.me/{username}?start=app",
                )
            ]
        ]
    )


async def get_bot_username() -> str | None:
    """Return bot username from env or Telegram API."""
    env_username = os.getenv("BOT_USERNAME", "").strip().lstrip("@")

    if env_username:
        return env_username

    try:
        me = await bot.get_me()
    except Exception:
        return None

    return (me.username or "").strip().lstrip("@") or None


async def answer_with_private_miniapp_button(message: Message, miniapp_url: str) -> None:
    """Send the WebApp button in a private chat."""
    await message.answer(
        "🚀 Турнирный портал Отца прогнозов\n\n"
        "Здесь удобнее делать прогнозы, смотреть таблицу, долгосроки, факты, квиз и архив.",
        reply_markup=build_private_miniapp_keyboard(miniapp_url),
    )


async def miniapp_handler(message: Message):
    """Send a Mini App entry point.

    Private chat:
    - Send a real Telegram WebApp button.

    Group chat:
    - Send a regular URL button to ``https://t.me/<bot>?start=app`` because
      Telegram rejects WebApp inline buttons in groups with BUTTON_TYPE_INVALID.
    """
    miniapp_url = get_miniapp_url()

    if not miniapp_url:
        await message.answer(
            "Mini App пока не настроен: добавь MINIAPP_URL или PUBLIC_BASE_URL."
        )
        return

    if message.chat.type != "private":
        bot_username = await get_bot_username()

        if not bot_username:
            await message.answer(
                "Не удалось определить username бота. "
                "Добавь переменную BOT_USERNAME в Railway без @."
            )
            return

        await message.answer(
            "🚀 Турнирный портал Отца прогнозов\n\n"
            "Mini App открывается в личке с ботом.\n"
            "Нажми кнопку ниже, а затем открой портал.",
            reply_markup=build_group_miniapp_keyboard(bot_username),
        )
        return

    await answer_with_private_miniapp_button(message, miniapp_url)
