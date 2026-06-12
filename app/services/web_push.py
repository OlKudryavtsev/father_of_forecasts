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

from app.models import PushSubscription


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


def notify_active_web_push_subscribers(db: Session, title: str, body: str, url: str = "/app") -> int:
    """Send Web Push notification to all active subscriptions."""
    if not web_push_enabled():
        return 0

    subscriptions = db.query(PushSubscription).filter(PushSubscription.is_active == True).all()
    sent = 0

    for subscription in subscriptions:
        if send_web_push_to_subscription(subscription, title=title, body=body, url=url):
            sent += 1

    db.commit()
    return sent
