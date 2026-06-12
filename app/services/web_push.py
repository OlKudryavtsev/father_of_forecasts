"""Optional Web Push helpers for PWA/browser notifications."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

try:
    from pywebpush import WebPushException, webpush
except Exception:  # pragma: no cover - optional dependency
    WebPushException = Exception
    webpush = None

from sqlalchemy.orm import Session

from app.constants.notifications import ADMIN_SETTING_BY_NOTIFICATION_KEY, NOTIFICATION_DEFAULTS
from app.models import AppSetting, PushSubscription, UserNotificationSetting


def web_push_enabled() -> bool:
    """Return whether Web Push is configured."""
    return bool(
        webpush
        and os.getenv("VAPID_PUBLIC_KEY", "").strip()
        and os.getenv("VAPID_PRIVATE_KEY", "").strip()
    )


def get_vapid_public_key() -> str | None:
    """Return VAPID public key for the frontend."""
    value = os.getenv("VAPID_PUBLIC_KEY", "").strip()
    return value or None


def _vapid_claims() -> dict:
    subject = os.getenv("VAPID_SUBJECT", "").strip() or "mailto:admin@example.com"
    return {"sub": subject}


def _global_notification_enabled(db: Session, notification_key: str) -> bool:
    """Return global admin switch for a notification type."""
    setting_key = ADMIN_SETTING_BY_NOTIFICATION_KEY.get(notification_key)
    if not setting_key:
        return True

    setting = db.query(AppSetting).filter(AppSetting.setting_key == setting_key).first()
    if not setting:
        return True

    return str(setting.setting_value).lower() == "true"


def _user_notification_enabled(db: Session, user_id: int, notification_key: str) -> bool:
    """Return whether a user enabled this notification type."""
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


def send_web_push_to_subscription(subscription: PushSubscription, title: str, body: str, url: str = "/app") -> bool:
    """Send one Web Push notification. Returns True on success."""
    if not web_push_enabled():
        return False

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "url": url,
        },
        ensure_ascii=False,
    )

    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh,
            "auth": subscription.auth,
        },
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=os.getenv("VAPID_PRIVATE_KEY", "").strip(),
            vapid_claims=_vapid_claims(),
        )
        subscription.last_success_at = datetime.now(timezone.utc)
        subscription.last_error = None
        return True
    except WebPushException as error:
        subscription.last_error = str(error)
        if getattr(error, "response", None) and getattr(error.response, "status_code", None) in {404, 410}:
            subscription.is_active = False
        return False
    except Exception as error:
        subscription.last_error = str(error)
        return False


def notify_web_push_subscribers_for_user(db: Session, user_id: int, title: str, body: str, url: str = "/app") -> int:
    """Send Web Push notification to one user's active browser/PWA subscriptions."""
    if not web_push_enabled():
        return 0

    subscriptions = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user_id, PushSubscription.is_active == True)
        .all()
    )
    sent = 0

    for subscription in subscriptions:
        if send_web_push_to_subscription(subscription, title=title, body=body, url=url):
            sent += 1

    db.commit()
    return sent


def notify_web_push_subscribers_for_user_if_enabled(
    db: Session,
    user_id: int,
    notification_key: str,
    title: str,
    body: str,
    url: str = "/app",
) -> int:
    """Send Web Push to one user only if global and personal settings allow it."""
    if not web_push_enabled():
        return 0
    if not _global_notification_enabled(db, notification_key):
        return 0
    if not _user_notification_enabled(db, user_id, notification_key):
        return 0
    return notify_web_push_subscribers_for_user(db, user_id=user_id, title=title, body=body, url=url)


def notify_active_web_push_subscribers(db: Session, title: str, body: str, url: str = "/app") -> int:
    """Send Web Push notification to all active subscriptions without settings filtering.

    Kept for admin/test use and backwards compatibility. For real app events use
    notify_active_web_push_subscribers_for_notification().
    """
    if not web_push_enabled():
        return 0

    subscriptions = db.query(PushSubscription).filter(PushSubscription.is_active == True).all()
    sent = 0

    for subscription in subscriptions:
        if send_web_push_to_subscription(subscription, title=title, body=body, url=url):
            sent += 1

    db.commit()
    return sent


def notify_active_web_push_subscribers_for_notification(
    db: Session,
    notification_key: str,
    title: str,
    body: str,
    url: str = "/app",
) -> int:
    """Send Web Push to active subscribers that enabled a notification type."""
    if not web_push_enabled():
        return 0
    if not _global_notification_enabled(db, notification_key):
        return 0

    subscriptions = db.query(PushSubscription).filter(PushSubscription.is_active == True).all()
    sent = 0
    user_setting_cache: dict[int, bool] = {}

    for subscription in subscriptions:
        user_id = int(subscription.user_id)
        if user_id not in user_setting_cache:
            user_setting_cache[user_id] = _user_notification_enabled(db, user_id, notification_key)
        if not user_setting_cache[user_id]:
            continue
        if send_web_push_to_subscription(subscription, title=title, body=body, url=url):
            sent += 1

    db.commit()
    return sent
