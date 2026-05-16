"""Real implementation extracted from the former bot_runtime monolith."""



def format_reminder_offset(minutes: int) -> str:
    """Provide bot helper logic for format_reminder_offset."""
    if minutes >= 1440:
        days = minutes // 1440

        if days == 1:
            return "24 часа"

        return f"{days} дн."

    if minutes >= 60:
        hours = minutes // 60

        if hours == 1:
            return "1 час"

        return f"{hours} часа"

    return f"{minutes} минут"


def format_team_with_flag(
        display_name: str,
        api_name: str | None = None,
        flag_before: bool = False,
) -> str:
    """Provide bot helper logic for format_team_with_flag."""
    from app.services.misc import get_team_flag

    flag = get_team_flag(display_name, api_name)

    if not flag:
        return display_name

    if flag_before:
        return f"{flag} {display_name}"

    return f"{display_name} {flag}"


def format_percent(part: int, total: int) -> str:
    """Provide bot helper logic for format_percent."""
    if total == 0:
        return "0%"

    return f"{round(part / total * 100)}%"

