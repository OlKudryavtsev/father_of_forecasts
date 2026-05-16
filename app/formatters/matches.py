"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import format_match, format_match_short_for_group, format_match, format_short_matches_fact, format_match_label, format_matches_list, format_missing_matches_list, format_match_result, format_user_match_prediction, build_match_card_text  # noqa: F401
