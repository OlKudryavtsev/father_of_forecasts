"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import get_group_chat_id, is_group_chat, get_or_create_user, is_private_chat, get_start_message_for_user  # noqa: F401
