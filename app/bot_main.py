"""Alternative bot entrypoint for modular imports.

Run with: `python -m app.bot_main`.
"""

import asyncio

from app.bot_runtime import main


if __name__ == "__main__":
    asyncio.run(main())
