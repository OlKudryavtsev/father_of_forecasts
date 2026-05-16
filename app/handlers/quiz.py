"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import private_quiz_handler, group_quiz_start_handler, quiz_handler, admin_import_quiz_handler, quiz_answer_callback, quiz_stats_handler, admin_quiz_stats_handler, quiz_category_callback, group_quiz_answer_callback, group_quiz_finish_handler, group_quiz_table_handler  # noqa: F401
