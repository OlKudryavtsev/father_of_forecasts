"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import build_admin_result_matches_keyboard, build_admin_result_score_keyboard, build_admin_result_winner_keyboard  # noqa: F401
