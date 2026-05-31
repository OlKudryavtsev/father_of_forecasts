"""Handlers for opening the Telegram Mini App portal."""

import os

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.runtime import Message


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


async def miniapp_handler(message: Message):
    """Send a button that opens the tournament portal Mini App."""
    miniapp_url = get_miniapp_url()

    if not miniapp_url:
        await message.answer(
            "Mini App пока не настроен: добавь MINIAPP_URL или PUBLIC_BASE_URL."
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть турнирный портал",
                    web_app=WebAppInfo(url=miniapp_url),
                )
            ]
        ]
    )

    await message.answer(
        "🚀 Турнирный портал Отца прогнозов\n\n"
        "Здесь удобнее делать прогнозы, смотреть таблицу, долгосроки, факты, квиз и архив.",
        reply_markup=keyboard,
    )
