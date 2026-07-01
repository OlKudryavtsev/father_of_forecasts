"""Telegram keyboards for the league-scoped synchronous quiz engine."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def quiz_miniapp_url(miniapp_url: str | None, session_id: int) -> str | None:
    """Attach a quiz id to the configured PWA URL without losing existing params."""
    if not miniapp_url:
        return None
    parsed = urlsplit(miniapp_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["quiz"] = str(session_id)
    query["tab"] = "quiz"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def _private_app_row(miniapp_url: str | None, session_id: int) -> list[InlineKeyboardButton] | None:
    url = quiz_miniapp_url(miniapp_url, session_id)
    if not url:
        return None
    return [
        InlineKeyboardButton(
            text="🧠 Открыть квиз в приложении",
            web_app=WebAppInfo(url=url),
        )
    ]


def build_private_quiz_registration_keyboard(session_id: int, miniapp_url: str | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="✅ Участвовать", callback_data=f"lqreg:{session_id}")]
    ]
    app_row = _private_app_row(miniapp_url, session_id)
    if app_row:
        rows.append(app_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_private_quiz_open_keyboard(session_id: int, miniapp_url: str | None) -> InlineKeyboardMarkup | None:
    app_row = _private_app_row(miniapp_url, session_id)
    return InlineKeyboardMarkup(inline_keyboard=[app_row]) if app_row else None


def build_private_quiz_question_keyboard(
    session_id: int,
    session_question_id: int,
    options: list[dict],
    selected_option_key: str | None,
    miniapp_url: str | None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for option in options:
        key = str(option.get("key") or "").upper().strip()
        text = str(option.get("text") or "").strip()
        marker = "✅ " if selected_option_key == key else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{marker}{key}. {text}",
                    callback_data=f"lqans:{session_id}:{session_question_id}:{key}",
                )
            ]
        )
    app_row = _private_app_row(miniapp_url, session_id)
    if app_row:
        rows.append(app_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_group_quiz_open_keyboard(bot_username: str | None, session_id: int, text: str = "🎮 Участвовать в квизе") -> InlineKeyboardMarkup | None:
    username = (bot_username or "").lstrip("@").strip()
    if not username:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    url=f"https://t.me/{username}?start=quiz_{session_id}",
                )
            ]
        ]
    )


def build_private_quiz_text_keyboard(
    session_id: int,
    session_question_id: int,
    miniapp_url: str | None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="✍️ Ввести ответ",
                callback_data=f"lqtext:{session_id}:{session_question_id}",
            )
        ]
    ]
    app_row = _private_app_row(miniapp_url, session_id)
    if app_row:
        rows.append(app_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)
