import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from app.db.d1 import (
    chunk_rows,
    d1_batch,
    has_binding,
    multi_row_insert,
    utcnow_naive,
    utcnow_text,
)
from app.db.session import QUERY_BUDGET


class _FakeStatement:
    def __init__(self, sql: str) -> None:
        self.sql = sql
        self.params: tuple = ()

    def bind(self, *params):
        self.params = params
        return self


class _FakeD1:
    def __init__(self) -> None:
        self.batch_arg: list[_FakeStatement] | None = None

    def prepare(self, sql: str) -> _FakeStatement:
        return _FakeStatement(sql)

    async def batch(self, statements):
        self.batch_arg = statements
        return ["ok"]


def test_d1_batch_passes_prepared_statements_directly():
    db = _FakeD1()
    env = SimpleNamespace(DB=db)

    result = asyncio.run(d1_batch(env, [("INSERT INTO t (a) VALUES (?)", [1])]))

    assert result == ["ok"]
    assert db.batch_arg is not None
    assert len(db.batch_arg) == 1
    assert db.batch_arg[0].sql == "INSERT INTO t (a) VALUES (?)"
    assert db.batch_arg[0].params == (1,)


def test_has_binding_detects_db_attribute():
    assert has_binding(SimpleNamespace(DB=object())) is True
    assert has_binding(SimpleNamespace()) is False
    assert has_binding(None) is False
    assert has_binding({"DB": object()}) is False


def test_utcnow_text_is_naive_utc_text():
    marker = datetime.now(UTC)
    before = marker.replace(tzinfo=None, microsecond=0)
    text = utcnow_text()
    parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S.%f")
    assert parsed >= before
    assert parsed.tzinfo is None
    assert utcnow_naive().tzinfo is None


def test_chunk_rows_respects_bound_parameter_limit():
    rows = [(index,) for index in range(10)]
    chunks = list(chunk_rows(rows, columns=2, max_params=4))
    assert [len(chunk) for chunk in chunks] == [2, 2, 2, 2, 2]
    assert [row for chunk in chunks for row in chunk] == rows


def test_chunk_rows_handles_empty_input():
    assert list(chunk_rows([], columns=3)) == []


def test_multi_row_insert_batches_and_parameterizes():
    rows = [(index, f"name-{index}", index % 2 == 0) for index in range(40)]
    statements = multi_row_insert("employees", ["id", "name", "active"], rows)

    assert len(statements) == 2
    total_params = 0
    for sql, params in statements:
        assert sql.startswith("INSERT INTO employees (id, name, active) VALUES ")
        assert sql.count("?") == len(params)
        assert len(params) <= 100
        total_params += len(params)
    assert total_params == len(rows) * 3


def test_multi_row_insert_chunks_by_column_count():
    rows = [(1, 2), (3, 4), (5, 6)]
    statements = multi_row_insert("pairs", ["a", "b"], rows)
    assert len(statements) == 1
    assert statements[0][1] == [1, 2, 3, 4, 5, 6]


def test_health_reports_query_count_header(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["X-Query-Count"] == "0"


def test_query_budget_is_positive():
    assert QUERY_BUDGET > 0
