"""Check that the connected database matches current SQLAlchemy models.

The script verifies that every table and every model column declared in
`app.models` exists in the target database.

It intentionally does not compare column types, constraints or indexes yet.
The goal is a fast safety check for deployments and Railway environments.
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect

from app.db import Base, engine
import app.models  # noqa: F401 - ensures model classes are registered in metadata


def collect_schema_diff() -> list[str]:
    """Return a list of missing tables/columns compared to app.models."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    errors: list[str] = []

    for table in Base.metadata.sorted_tables:
        table_name = table.name

        if table_name not in existing_tables:
            errors.append(f"Missing table: {table_name}")
            continue

        existing_columns = {
            column["name"]
            for column in inspector.get_columns(table_name)
        }

        expected_columns = {
            column.name
            for column in table.columns
        }

        for column_name in sorted(expected_columns - existing_columns):
            errors.append(f"Missing column: {table_name}.{column_name}")

    return errors


def main() -> int:
    """Run schema check and return process exit code."""
    errors = collect_schema_diff()

    if errors:
        print("DB schema check failed.")
        print()

        for error in errors:
            print(f"- {error}")

        return 1

    print("DB schema check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
