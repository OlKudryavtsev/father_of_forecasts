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
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qsl

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import User, WebSession
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

        if admin_status and getattr(user, "access_status", "approved") != "approved":
            user.access_status = "approved"
            user.approved_at = user.approved_at or datetime.now(timezone.utc)
            changed = True

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
        access_status="approved" if admin_status else "pending",
        approved_at=datetime.now(timezone.utc) if admin_status else None,
        access_requested_at=datetime.now(timezone.utc),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user



def _web_session_secret() -> str:
    """Return stable secret for hashing browser session tokens."""
    return (
        os.getenv("WEB_SESSION_SECRET", "").strip()
        or os.getenv("BOT_TOKEN", "").strip()
        or "dev-web-session-secret"
    )


def hash_web_session_token(token: str) -> str:
    """Hash raw web session token before storing it in DB."""
    return hmac.new(
        key=_web_session_secret().encode("utf-8"),
        msg=token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def create_web_session_for_user(
    db: Session,
    user: User,
    user_agent: str | None = None,
    title: str | None = None,
) -> tuple[str, WebSession]:
    """Create a browser/PWA session token linked to current Telegram user."""
    raw_token = secrets.token_urlsafe(32)
    days = int(os.getenv("WEB_SESSION_TTL_DAYS", "180"))
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)

    session = WebSession(
        user_id=user.id,
        token_hash=hash_web_session_token(raw_token),
        title=title or "iPhone / browser",
        user_agent=user_agent,
        is_active=True,
        expires_at=expires_at,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return raw_token, session


def get_user_from_web_session(db: Session, raw_token: str) -> User:
    """Resolve browser/PWA session token to local user."""
    token_hash = hash_web_session_token(raw_token)
    now = datetime.now(timezone.utc)

    session = (
        db.query(WebSession)
        .filter(
            WebSession.token_hash == token_hash,
            WebSession.is_active == True,
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Web session is invalid",
        )

    if session.expires_at and session.expires_at < now:
        session.is_active = False
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Web session is expired",
        )

    session.last_used_at = now
    db.commit()

    return session.user

def _ensure_approved_for_web(user: User) -> User:
    status_value = getattr(user, "access_status", "approved") or "approved"
    if status_value != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Access request is pending approval"
                if status_value == "pending"
                else "Access is not approved"
            ),
        )
    return user



def get_current_user(
    db: Session = Depends(get_db),
    init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    web_session_token: str | None = Header(default=None, alias="X-Web-Session-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    web_session_cookie: str | None = Cookie(default=None, alias="ff_web_session"),
) -> User:
    """FastAPI dependency returning the authenticated local user."""
    debug_telegram_id = os.getenv("MINIAPP_DEBUG_TELEGRAM_ID", "").strip()

    bearer_token = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization.split(" ", 1)[1].strip()

    raw_web_token = (web_session_token or bearer_token or web_session_cookie or "").strip()

    # Prefer fresh Telegram initData when Mini App runs inside Telegram.
    # This prevents a stale browser token in localStorage from breaking Telegram mode.
    if not init_data and raw_web_token:
        return _ensure_approved_for_web(get_user_from_web_session(db, raw_web_token))

    if not init_data and debug_telegram_id:
        debug_user = TelegramMiniAppUser(
            id=int(debug_telegram_id),
            username=os.getenv("MINIAPP_DEBUG_USERNAME") or "debug",
            first_name=os.getenv("MINIAPP_DEBUG_FIRST_NAME") or "Debug",
            last_name=os.getenv("MINIAPP_DEBUG_LAST_NAME") or "User",
        )
        return _ensure_approved_for_web(get_or_create_user_from_telegram(db, debug_user))

    if not init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Telegram-Init-Data header is required",
        )

    telegram_user = parse_telegram_user_from_init_data(init_data)
    return _ensure_approved_for_web(get_or_create_user_from_telegram(db, telegram_user))
