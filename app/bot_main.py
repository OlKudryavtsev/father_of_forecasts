"""Alternative module entrypoint for running the Telegram bot.

Usage:
    python -m app.bot_main
"""

import asyncio

from app.bot_runtime import main


if __name__ == "__main__":
    asyncio.run(main())
