"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import admin_handler, admin_set_result_handler, admin_recalculate_handler, admin_reminders_status_handler, admin_result_score_callback, admin_result_winner_callback, admin_result_custom_callback, admin_result_custom_score_handler, admin_sync_wc2026_schedule_handler, admin_sync_results_handler, admin_rankings_check_handler, admin_notify_test_handler, admin_command_stats_handler, admin_command_stats_user_handler  # noqa: F401
