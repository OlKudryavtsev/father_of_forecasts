"""Compatibility entrypoint for the Telegram bot.

The full current runtime is kept in app.bot_runtime during the first safe
refactoring stage. This file preserves the original Railway/local command
`python bot.py` without changing bot behavior.
"""

import asyncio

from app.bot_runtime import main


if __name__ == "__main__":
    asyncio.run(main())
