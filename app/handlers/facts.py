"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import fact_handler, admin_facts_count_handler, admin_import_facts_handler, admin_daily_fact_preview_handler, fact_category_callback, admin_send_daily_fact_group_handler  # noqa: F401
