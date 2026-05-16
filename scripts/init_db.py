"""Create missing database tables from SQLAlchemy models.

This script is useful for local setup or for initializing a new empty database.

It uses SQLAlchemy `Base.metadata.create_all`, so it creates tables that do not
exist yet. It does not perform schema migrations for existing tables/columns.
For production schema evolution, prefer Alembic migrations.
"""

from app.db import Base, engine
import app.models  # noqa: F401 - ensures model classes are registered in metadata


def main() -> None:
    """Create all missing tables declared in app.models."""
    Base.metadata.create_all(bind=engine)
    print("DB schema created/verified.")


if __name__ == "__main__":
    main()
