"""Alternative module entrypoint for the bot."""

from app.bot_runtime import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
