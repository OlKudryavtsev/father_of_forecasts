"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def shorten_table_name(name: str, max_len: int = 10) -> str:
    """Provide bot helper logic for shorten_table_name."""
    if not name:
        return "Игрок"

    if len(name) <= max_len:
        return name

    return name[:max_len - 1] + "…"

