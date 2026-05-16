"""Real implementation extracted from the former bot_runtime monolith."""


from app.runtime import (
    APP_TIMEZONE,
    CommandLog,
    Message,
    User,
    datetime,
    os,
    timedelta,
    timezone,
)

def get_admin_telegram_ids() -> list[int]:
    """Provide bot helper logic for get_admin_telegram_ids."""
    raw_value = os.getenv("ADMIN_TELEGRAM_IDS", "")

    admin_ids = []

    for item in raw_value.split(","):
        item = item.strip()

        if item.isdigit():
            admin_ids.append(int(item))

    return admin_ids


def get_today_moscow_range_utc() -> tuple[datetime, datetime]:
    """Provide bot helper logic for get_today_moscow_range_utc."""
    now_moscow = datetime.now(APP_TIMEZONE)

    start_moscow = now_moscow.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_moscow = start_moscow + timedelta(days=1)

    return (
        start_moscow.astimezone(timezone.utc),
        end_moscow.astimezone(timezone.utc),
    )


def build_command_stats_for_period(
        db,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit_users: int = 20,
) -> list[dict]:
    """Provide bot helper logic for build_command_stats_for_period."""
    query = db.query(CommandLog)

    if start_at:
        query = query.filter(CommandLog.created_at >= start_at)

    if end_at:
        query = query.filter(CommandLog.created_at < end_at)

    logs = query.order_by(CommandLog.created_at.desc()).all()

    stats_by_user = {}

    for log in logs:
        key = log.user_id or f"tg:{log.telegram_id}"

        if key not in stats_by_user:
            stats_by_user[key] = {
                "display_name": log.display_name or f"Telegram {log.telegram_id}",
                "telegram_id": log.telegram_id,
                "total": 0,
                "commands": {},
                "last_command": None,
                "last_at": None,
            }

        row = stats_by_user[key]

        row["total"] += 1
        row["commands"][log.command] = row["commands"].get(log.command, 0) + 1

        if row["last_at"] is None or log.created_at > row["last_at"]:
            row["last_at"] = log.created_at
            row["last_command"] = log.command

    rows = list(stats_by_user.values())

    rows.sort(
        key=lambda item: item["total"],
        reverse=True,
    )

    return rows[:limit_users]


def is_user_admin(user: User) -> bool:
    """Provide bot helper logic for is_user_admin."""
    return bool(user.is_admin)


def is_private_chat(message: Message) -> bool:
    """Provide bot helper logic for is_private_chat."""
    return message.chat.type == "private"


def ensure_admin_or_reply(user: User) -> bool:
    """Provide bot helper logic for ensure_admin_or_reply."""
    return bool(user.is_admin)


def extract_command_from_text(text: str | None) -> str | None:
    """Provide bot helper logic for extract_command_from_text."""
    if not text:
        return None

    first_part = text.strip().split()[0]

    if not first_part.startswith("/"):
        return None

    # Если команда пришла как /start@bot_name
    command = first_part.split("@")[0]

    return command.lower()

