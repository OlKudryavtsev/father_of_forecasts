"""Real implementation extracted from the former bot_runtime monolith."""


from app.formatters.matches import format_datetime

def format_command_stats_block(title: str, rows: list[dict]) -> list[str]:
    """Provide bot helper logic for format_command_stats_block."""
    lines = [title]

    if not rows:
        lines.append("Нет данных.")
        return lines

    for index, row in enumerate(rows, start=1):
        commands_sorted = sorted(
            row["commands"].items(),
            key=lambda item: item[1],
            reverse=True,
        )

        top_commands = ", ".join(
            f"{command} {count}"
            for command, count in commands_sorted[:5]
        )

        last_text = ""

        if row["last_at"] and row["last_command"]:
            last_text = (
                f"\n   последний: {row['last_command']} "
                f"в {format_datetime(row['last_at'])}"
            )

        lines.append(
            f"{index}. {row['display_name']} — {row['total']} выз."
            f"{last_text}\n"
            f"   {top_commands}"
        )

    return lines

