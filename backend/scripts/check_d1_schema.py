"""Check that the D1 migration schema and the SQLAlchemy metadata agree.

Only table and named index names are compared, not column SQL: D1 and
SQLAlchemy emit slightly different DDL for the same logical schema.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app.models  # noqa: F401,E402
from app.db.base import Base  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "d1"


def _load_migrations() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        connection.executescript(path.read_text(encoding="utf-8"))
    return connection


def main() -> int:
    connection = _load_migrations()
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    indexes = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND name NOT LIKE 'sqlite_autoindex%'"
        )
    }

    metadata_tables = set(Base.metadata.tables)
    metadata_indexes = {
        index.name for table in Base.metadata.tables.values() for index in table.indexes
    }

    ok = True
    missing_tables = metadata_tables - tables
    extra_tables = tables - metadata_tables
    missing_indexes = metadata_indexes - indexes
    extra_indexes = indexes - metadata_indexes

    if missing_tables:
        ok = False
        print(f"Missing D1 tables: {sorted(missing_tables)}")
    if extra_tables:
        ok = False
        print(f"Extra D1 tables: {sorted(extra_tables)}")
    if missing_indexes:
        ok = False
        print(f"Missing D1 indexes: {sorted(missing_indexes)}")
    if extra_indexes:
        print(f"Note: D1-only indexes: {sorted(extra_indexes)}")

    if ok:
        print("D1 schema matches SQLAlchemy metadata.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
