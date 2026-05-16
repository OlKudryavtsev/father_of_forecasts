"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import parse_score, get_today_moscow_range_utc, get_team_flag, get_days_until_wc2026, send_long_message, main  # noqa: F401
