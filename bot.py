"""Entrypoint for Railway/local launch.

All implementation lives in modular app.* modules.  Ensure new durable cache
models exist before the bot starts its background workers; the web process also
runs the same idempotent metadata initialization.
"""

from app.db import Base, engine
from app import models as _models  # noqa: F401 - register every SQLAlchemy model
from app.bot_runtime import main

if __name__ == "__main__":
    import asyncio

    Base.metadata.create_all(bind=engine)
    asyncio.run(main())
