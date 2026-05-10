import os

from fastapi import Header, HTTPException


def get_admin_telegram_ids() -> set[int]:
    raw_value = os.getenv("ADMIN_TELEGRAM_IDS", "")

    admin_ids = set()

    for item in raw_value.split(","):
        item = item.strip()

        if item.isdigit():
            admin_ids.add(int(item))

    return admin_ids


def is_admin_telegram_id(telegram_id: int) -> bool:
    return telegram_id in get_admin_telegram_ids()


def require_admin_api_token(x_admin_token: str | None = Header(default=None)):
    expected_token = os.getenv("ADMIN_API_TOKEN")

    if not expected_token:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_API_TOKEN is not configured",
        )

    if x_admin_token != expected_token:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    return True