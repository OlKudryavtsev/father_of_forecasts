"""Entrypoint for Railway/local launch.

All implementation lives in modular app.* modules.
"""

from app.bot_runtime import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
