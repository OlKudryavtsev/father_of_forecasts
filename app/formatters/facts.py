"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import format_ranking_fact, format_h2h_fact, format_world_cup_fact, plural_days_ru  # noqa: F401
