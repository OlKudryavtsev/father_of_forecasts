import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

# Railway иногда отдает postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def ensure_schema() -> None:
    """Create missing SQLAlchemy tables without a concurrent PostgreSQL DDL race.

    Railway starts the bot and Uvicorn from the same container.  PostgreSQL
    ``CREATE TABLE IF NOT EXISTS`` semantics used internally by SQLAlchemy are
    not safe when both processes inspect and create a brand-new table at the
    exact same time. A transaction-scoped advisory lock makes that bootstrap
    single-writer while keeping SQLite/local development unchanged.
    """
    if engine.dialect.name != "postgresql":
        Base.metadata.create_all(bind=engine)
        return

    lock_key = 20260704_376
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
        Base.metadata.create_all(bind=connection)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()