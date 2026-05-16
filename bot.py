"""Telegram bot entrypoint.

This compatibility entrypoint keeps the original runtime behavior while the codebase is
being split into modules. The executable implementation is in `app.bot_runtime`.
"""

import asyncio

from app.bot_runtime import main


if __name__ == "__main__":
    asyncio.run(main())
