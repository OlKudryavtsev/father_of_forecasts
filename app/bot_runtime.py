"""Application bootstrap for the modular Father Predictions bot.

This module imports domain modules, injects shared symbols for backward-compatible
function lookup, registers middleware and starts polling.
"""

import asyncio
import importlib

from app.runtime import bot, dp, DAILY_FACTS_ENABLED
from app.middleware.access import (
    CommandLoggingMiddleware,
    GroupCallbackAccessMiddleware,
    GroupCommandAccessMiddleware,
)

MODULE_NAMES = [
    "app.constants.categories",
    "app.constants.commands",
    "app.constants.teams",
    "app.constants.texts",
    "app.formatters.admin",
    "app.formatters.archive",
    "app.formatters.facts",
    "app.formatters.forecast",
    "app.formatters.matches",
    "app.formatters.misc",
    "app.formatters.predictions",
    "app.formatters.quiz",
    "app.formatters.table",
    "app.jobs.daily_facts",
    "app.jobs.misc",
    "app.jobs.reminders",
    "app.keyboards.admin",
    "app.keyboards.archive",
    "app.keyboards.facts",
    "app.keyboards.matches",
    "app.keyboards.panini",
    "app.keyboards.predictions",
    "app.keyboards.quiz",
    "app.keyboards.table",
    "app.middleware.access",
    "app.repositories.archive",
    "app.repositories.facts",
    "app.repositories.matches",
    "app.repositories.predictions",
    "app.repositories.quiz",
    "app.repositories.tournament",
    "app.repositories.users",
    "app.services.admin",
    "app.services.archive",
    "app.services.facts",
    "app.services.forecast",
    "app.services.matches",
    "app.services.misc",
    "app.services.notifications",
    "app.services.panini",
    "app.services.predictions",
    "app.services.quiz",
    "app.services.table",
    "app.services.tournament",
    "app.services.users",
    "app.states",
    "app.handlers.admin",
    "app.handlers.archive",
    "app.handlers.facts",
    "app.handlers.forecast",
    "app.handlers.help",
    "app.handlers.matches",
    "app.handlers.misc",
    "app.handlers.panini",
    "app.handlers.predictions",
    "app.handlers.quiz",
    "app.handlers.start",
    "app.handlers.table",
    "app.handlers.tournament",
]

_modules = [importlib.import_module(name) for name in MODULE_NAMES]

# Backward-compatible symbol injection: extracted functions keep their original
# bodies and can resolve helpers that now live in neighboring modules.
_public_symbols = {}
for _module in _modules:
    for _name, _value in vars(_module).items():
        if not _name.startswith("_"):
            _public_symbols[_name] = _value

for _module in _modules:
    vars(_module).update(_public_symbols)

# Make symbols available from app.bot_runtime for legacy imports, if any.
globals().update(_public_symbols)

dp.message.middleware(GroupCommandAccessMiddleware())
dp.message.middleware(CommandLoggingMiddleware())
dp.callback_query.middleware(GroupCallbackAccessMiddleware())


async def main():
    """Start background jobs and run aiogram polling."""
    if _public_symbols["reminders_enabled"]():
        asyncio.create_task(_public_symbols["reminders_loop"]())

    if DAILY_FACTS_ENABLED:
        asyncio.create_task(_public_symbols["daily_facts_loop"]())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
