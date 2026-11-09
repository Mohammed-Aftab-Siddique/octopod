"""Create the first administrator on a D1 database.

There is no public admin-creation endpoint. This script hashes the password with
the application's Argon2 parameters and executes an INSERT through Wrangler.

Examples::

    uv run python scripts/create_admin.py --local --email you@example.com
    uv run python scripts/create_admin.py --remote --email you@example.com
    uv run python scripts/create_admin.py --print-sql --email you@example.com
"""

import argparse
import getpass
import subprocess
import sys

from argon2 import PasswordHasher


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_sql(email: str, password_hash: str) -> str:
    return (
        "INSERT INTO users (email, password_hash, role, is_active, created_at, updated_at) "
        f"VALUES ({_sql_literal(email.lower())}, {_sql_literal(password_hash)}, "
        "'admin', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", help="Prompted for when omitted")
    parser.add_argument("--database", default="octopod")
    parser.add_argument("--local", action="store_true", help="Use the local D1 database")
    parser.add_argument("--remote", action="store_true", help="Use the remote D1 database")
    parser.add_argument("--print-sql", action="store_true", help="Print SQL instead of executing")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Admin password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 2

    sql = build_sql(args.email, PasswordHasher().hash(password))
    if args.print_sql:
        print(sql)
        return 0

    command = ["npx", "wrangler", "d1", "execute", args.database]
    command.append("--local" if args.local else "--remote")
    command.extend(["--command", sql])
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
