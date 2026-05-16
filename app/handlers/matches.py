"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import matches_handler, match_handler, admin_matches_handler, admin_matches_all_handler, admin_edit_match_handler, admin_delete_match_handler, admin_force_delete_match_handler, match_custom_score_handler, matches_all_handler, admin_import_matches_handler, match_handler, admin_result_match_callback, match_card_callback  # noqa: F401
