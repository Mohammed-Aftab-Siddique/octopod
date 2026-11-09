"""Export a D1 (SQLite) database back to PostgreSQL-compatible SQL.

Use this when rolling back after users have written to D1. Start from a
``wrangler d1 export`` file::

    npx wrangler d1 export octopod --remote --output /tmp/octopod-d1.sql
    sqlite3 /tmp/octopod-d1.sqlite ".read /tmp/octopod-d1.sql"   # or use --output

Then::

    uv run python scripts/export_d1_to_postgres.py \
        --sqlite /tmp/octopod-d1.sqlite --out /tmp/octopod-rollback.sql
"""

import argparse
import json
import sys
from datetime import UTC, date, datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, MetaData, create_engine, select

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


def _literal(value, column_type) -> str:
    if value is None:
        return "NULL"
    if isinstance(column_type, Boolean):
        return "TRUE" if bool(value) else "FALSE"
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return "'" + value.strftime("%Y-%m-%d %H:%M:%S.%f") + "'"
    if isinstance(value, date):
        return "'" + value.isoformat() + "'"
    if isinstance(column_type, JSON) or isinstance(value, (dict, list)):
        value = json.dumps(value) if not isinstance(value, str) else value
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return "decode('" + value.hex() + "', 'hex')"
    return "'" + str(value).replace("'", "''") + "'"


def export(sqlite_path: str, out_path: str) -> dict[str, int]:
    engine = create_engine(f"sqlite:///{sqlite_path}", future=True)
    metadata = MetaData()
    metadata.reflect(bind=engine)

    counts: dict[str, int] = {}
    with engine.connect() as connection, open(out_path, "w", encoding="utf-8") as out:
        out.write("-- Octopod D1 -> PostgreSQL rollback export\n")
        out.write("SET session_replication_role = replica;\n")
        for table_name in TABLES:
            table = metadata.tables.get(table_name)
            if table is None:
                continue
            rows = connection.execute(select(table)).mappings().all()
            columns = [column.name for column in table.columns]
            column_sql = ", ".join(columns)
            for row in rows:
                values = ", ".join(
                    _literal(row[name], table.columns[name].type) for name in columns
                )
                out.write(f"INSERT INTO {table_name} ({column_sql}) VALUES ({values});\n")
            counts[table_name] = len(rows)
            print(f"{table_name}: {len(rows)} rows")
        out.write("SET session_replication_role = DEFAULT;\n")
        out.write("-- Reset integer sequences after importing explicit ids.\n")
        for table_name in TABLES:
            if table_name in counts:
                out.write(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table_name}), 1));\n"
                )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", required=True, help="Path to the D1 SQLite export")
    parser.add_argument("--out", required=True, help="Path to write PostgreSQL SQL")
    args = parser.parse_args()
    try:
        export(args.sqlite, args.out)
    except Exception as exc:  # noqa: BLE001
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
