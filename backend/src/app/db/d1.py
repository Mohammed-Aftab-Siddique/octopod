"""Helpers for the D1 Worker binding.

D1 has no interactive transactions. ``env.DB.batch([...])`` executes all
statements in one implicit transaction and counts as a single query against the
per-invocation query limit, which is what makes bulk roster writes fit on the
Workers Free plan.

The Pyodide imports live inside the functions so this module stays importable in
the local SQLite test environment.
"""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

MAX_BOUND_PARAMS = 100


def has_binding(env) -> bool:
    """Return True when the request is running with a D1 binding."""

    return env is not None and getattr(env, "DB", None) is not None


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def utcnow_text() -> str:
    """Naive UTC timestamp in the text format SQLite stores for DATETIME."""

    return utcnow_naive().strftime("%Y-%m-%d %H:%M:%S.%f")


async def d1_batch(env, statements: Sequence[tuple[str, Sequence]]) -> list:
    """Execute prepared statements as one atomic D1 batch (one query).

    Pass the list directly: the Workers Python runtime wraps bindings and
    converts Python values for RPC calls. Converting with ``to_js`` instead
    creates borrowed proxies that are destroyed before the batch completes.
    """

    prepared = [env.DB.prepare(sql).bind(*params) for sql, params in statements]
    return await env.DB.batch(prepared)


async def d1_all(env, sql: str, params: Sequence = ()) -> list[dict[str, Any]]:
    """Run a read query and return rows as plain dictionaries."""

    result = await env.DB.prepare(sql).bind(*params).all()
    rows = getattr(result, "results", None)
    if rows is None:
        rows = result
    if hasattr(rows, "to_py"):
        rows = rows.to_py()
    return [dict(row) for row in rows]


async def d1_first(env, sql: str, params: Sequence = ()) -> dict[str, Any] | None:
    rows = await d1_all(env, sql, params)
    return rows[0] if rows else None


def chunk_rows(
    rows: Sequence[Sequence], columns: int, max_params: int = MAX_BOUND_PARAMS
) -> Iterable[Sequence[Sequence]]:
    """Yield chunks that stay under D1's bound-parameter limit."""

    size = max(1, max_params // columns)
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def multi_row_insert(
    table: str, columns: Sequence[str], rows: Sequence[Sequence]
) -> list[tuple[str, Sequence]]:
    """Build parameterized multi-row INSERT statements."""

    column_sql = ", ".join(columns)
    placeholder = "(" + ", ".join("?" for _ in columns) + ")"
    statements: list[tuple[str, Sequence]] = []
    for chunk in chunk_rows(rows, len(columns)):
        values_sql = ", ".join(placeholder for _ in chunk)
        params = [value for row in chunk for value in row]
        statements.append((f"INSERT INTO {table} ({column_sql}) VALUES {values_sql}", params))
    return statements
