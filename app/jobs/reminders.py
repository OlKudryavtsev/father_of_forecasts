"""Real implementation extracted from the former bot_runtime monolith."""


from app.runtime import Match, ReminderLog, User, asyncio, os

def reminders_enabled() -> bool:
    """Provide bot helper logic for reminders_enabled."""
    return os.getenv("REMINDERS_ENABLED", "false").lower() == "true"


def get_reminder_offsets_minutes() -> list[int]:
    """Provide bot helper logic for get_reminder_offsets_minutes."""
    raw_value = os.getenv("REMINDER_OFFSETS_MINUTES", "1440,180,30")

    offsets = []

    for item in raw_value.split(","):
        item = item.strip()

        if item.isdigit():
            offsets.append(int(item))

    return sorted(offsets, reverse=True)


def get_reminder_check_interval_seconds() -> int:
    """Provide bot helper logic for get_reminder_check_interval_seconds."""
    raw_value = os.getenv("REMINDER_CHECK_INTERVAL_SECONDS", "60")

    if raw_value.isdigit():
        return int(raw_value)

    return 60


def reminder_was_sent(
        db,
        user: User,
        match: Match,
        reminder_type: str,
        reminder_key: str,
) -> bool:
    """Provide bot helper logic for reminder_was_sent."""
    existing_log = db.query(ReminderLog).filter(
        ReminderLog.user_id == user.id,
        ReminderLog.match_id == match.id,
        ReminderLog.reminder_type == reminder_type,
        ReminderLog.reminder_key == reminder_key,
    ).first()

    return existing_log is not None


def mark_reminder_sent(
        db,
        user: User,
        match: Match,
        reminder_type: str,
        reminder_key: str,
):
    """Provide bot helper logic for mark_reminder_sent."""
    log = ReminderLog(
        user_id=user.id,
        match_id=match.id,
        reminder_type=reminder_type,
        reminder_key=reminder_key,
    )

    db.add(log)
    db.commit()


async def reminders_loop():
    """Handle asynchronous bot workflow for reminders_loop."""
    if not reminders_enabled():
        print("Reminders are disabled")
        return

    interval_seconds = get_reminder_check_interval_seconds()

    print(
        "Reminders loop started. "
        f"Interval: {interval_seconds} seconds. "
        f"Offsets: {get_reminder_offsets_minutes()} minutes."
    )

    await asyncio.sleep(10)

    while True:
        try:
            from app.services.matches import send_match_reminders_once

            await send_match_reminders_once()
        except Exception as error:
            print(f"Reminder loop error: {error}")

        await asyncio.sleep(interval_seconds)

