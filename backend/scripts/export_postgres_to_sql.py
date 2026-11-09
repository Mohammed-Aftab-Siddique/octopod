"""Export an existing Octopod database to a D1-compatible SQL file.

The script is a local migration tool, not a Worker. It preserves primary keys
and password hashes, inserts parent tables before children (D1 enforces foreign
keys), and prints per-table row counts.

Usage::

    uv run python scripts/export_postgres_to_sql.py \
        --database-url "postgresql+psycopg://..." \
        --out /tmp/octopod-data.sql
"""

import argparse
import json
import sys
from datetime import UTC, date, datetime
from enum import Enum

from sqlalchemy import MetaData, create_engine, select

# Dependency order matters because D1 enforces foreign keys.
TABLES = [
    "employees",
    "holidays",
    "shift_statuses",
    "staffing_requirements",
    "users",
    "availability",
    "roster_periods",
    "user_sessions",
    "generation_runs",
    "roster_assignments",
]


def _literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return "'" + value.strftime("%Y-%m-%d %H:%M:%S.%f") + "'"
    if isinstance(value, date):
        return "'" + value.isoformat() + "'"
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return "X'" + value.hex() + "'"
    return "'" + str(value).replace("'", "''") + "'"


def export(database_url: str, out_path: str, include_sessions: bool) -> dict[str, int]:
    engine = create_engine(database_url, future=True)
    metadata = MetaData()
    metadata.reflect(bind=engine)

    counts: dict[str, int] = {}
    with engine.connect() as connection, open(out_path, "w", encoding="utf-8") as out:
        out.write("-- Octopod data export for Cloudflare D1\n")
        for table_name in TABLES:
            if table_name == "user_sessions" and not include_sessions:
                continue
            table = metadata.tables.get(table_name)
            if table is None:
                continue
            rows = connection.execute(select(table)).mappings().all()
            columns = [column.name for column in table.columns]
            column_sql = ", ".join(columns)
            for row in rows:
                values = ", ".join(_literal(row[name]) for name in columns)
                out.write(f"INSERT INTO {table_name} ({column_sql}) VALUES ({values});\n")
            counts[table_name] = len(rows)
            print(f"{table_name}: {len(rows)} rows")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--include-sessions", action="store_true")
    args = parser.parse_args()

    try:
        export(args.database_url, args.out, args.include_sessions)
    except Exception as exc:  # noqa: BLE001 - CLI should print a useful message
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
