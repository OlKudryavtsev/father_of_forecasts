"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import format_datetime, format_reminder_offset, format_team_with_flag, build_user_summary_context, format_daily_world_cup_rubric, format_percent  # noqa: F401
