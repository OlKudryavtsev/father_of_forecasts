"""Telegram Mini App authentication helpers.

The Mini App sends Telegram `initData` to the backend in the
`X-Telegram-Init-Data` header. The backend verifies the HMAC hash using the
bot token and maps the Telegram user to a local `users` row.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import User
from app.admin import is_admin_telegram_id


@dataclass(frozen=True)
class TelegramMiniAppUser:
    """User payload extracted from validated Telegram WebApp initData."""

    id: int
    username: str | None
    first_name: str | None
    last_name: str | None

    @property
    def display_name(self) -> str:
        """Return a human-friendly display name for the Telegram user."""
        parts = [self.first_name, self.last_name]
        full_name = " ".join(part for part in parts if part).strip()

        if full_name:
            return full_name

        if self.username:
            return f"@{self.username}"

        return f"Telegram {self.id}"


def get_db():
    """Yield a SQLAlchemy session for FastAPI dependencies."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _get_bot_token() -> str:
    """Return BOT_TOKEN or fail with a server configuration error."""
    token = os.getenv("BOT_TOKEN", "").strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BOT_TOKEN is not configured",
        )

    return token


def _validate_init_data_hash(init_data: str, bot_token: str) -> dict[str, str]:
    """Validate Telegram WebApp initData and return parsed key-value pairs."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)

    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram initData hash is missing",
        )

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(pairs.items())
    )

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram initData hash",
        )

    return pairs


def parse_telegram_user_from_init_data(init_data: str) -> TelegramMiniAppUser:
    """Validate initData and return the Telegram user payload."""
    payload = _validate_init_data_hash(init_data, _get_bot_token())

    auth_date_raw = payload.get("auth_date")
    max_age_seconds = int(os.getenv("MINIAPP_AUTH_MAX_AGE_SECONDS", "86400"))

    if auth_date_raw and auth_date_raw.isdigit():
        auth_age = int(time.time()) - int(auth_date_raw)

        if auth_age > max_age_seconds:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Telegram initData is expired",
            )

    user_raw = payload.get("user")

    if not user_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram user payload is missing",
        )

    try:
        user_payload: dict[str, Any] = json.loads(user_raw)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram user payload is invalid",
        ) from error

    telegram_id = user_payload.get("id")

    if telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram user id is missing",
        )

    return TelegramMiniAppUser(
        id=int(telegram_id),
        username=user_payload.get("username"),
        first_name=user_payload.get("first_name"),
        last_name=user_payload.get("last_name"),
    )


def get_or_create_user_from_telegram(db: Session, telegram_user: TelegramMiniAppUser) -> User:
    """Create or update a local user from Telegram Mini App user data."""
    admin_status = is_admin_telegram_id(telegram_user.id)

    user = db.query(User).filter(User.telegram_id == telegram_user.id).first()

    if user:
        changed = False

        if user.username != telegram_user.username:
            user.username = telegram_user.username
            changed = True

        if user.display_name != telegram_user.display_name:
            user.display_name = telegram_user.display_name
            changed = True

        if user.is_admin != admin_status:
            user.is_admin = admin_status
            changed = True

        if changed:
            db.commit()
            db.refresh(user)

        return user

    user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        display_name=telegram_user.display_name,
        is_admin=admin_status,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_current_user(
    db: Session = Depends(get_db),
    init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
) -> User:
    """FastAPI dependency returning the authenticated local user."""
    debug_telegram_id = os.getenv("MINIAPP_DEBUG_TELEGRAM_ID", "").strip()

    if not init_data and debug_telegram_id:
        debug_user = TelegramMiniAppUser(
            id=int(debug_telegram_id),
            username=os.getenv("MINIAPP_DEBUG_USERNAME") or "debug",
            first_name=os.getenv("MINIAPP_DEBUG_FIRST_NAME") or "Debug",
            last_name=os.getenv("MINIAPP_DEBUG_LAST_NAME") or "User",
        )
        return get_or_create_user_from_telegram(db, debug_user)

    if not init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Telegram-Init-Data header is required",
        )

    telegram_user = parse_telegram_user_from_init_data(init_data)
    return get_or_create_user_from_telegram(db, telegram_user)
