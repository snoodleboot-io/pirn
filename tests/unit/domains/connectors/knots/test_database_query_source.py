"""Tests for :class:`DatabaseQuerySource` against an in-memory SqlitePool."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.connectors.knots.database_query_source import DatabaseQuerySource
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    await p.execute("INSERT INTO users (id, name) VALUES (?, ?)", (1, "alice"))
    await p.execute("INSERT INTO users (id, name) VALUES (?, ?)", (2, "bob"))
    yield p
    await p.close()


@pytest.mark.asyncio
async def test_query_returns_rows(pool: SqlitePool) -> None:
    with Tapestry() as t:
        DatabaseQuerySource(
            pool=pool,
            query="SELECT id, name FROM users ORDER BY id",
            _config=KnotConfig(id="users"),
        )

    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["users"] == [(1, "alice"), (2, "bob")]


@pytest.mark.asyncio
async def test_query_with_parameters(pool: SqlitePool) -> None:
    with Tapestry() as t:
        DatabaseQuerySource(
            pool=pool,
            query="SELECT name FROM users WHERE id = ?",
            parameters=(2,),
            _config=KnotConfig(id="user"),
        )

    result = await t.run(RunRequest())
    assert result.outputs["user"] == [("bob",)]


def test_construct_rejects_non_pool() -> None:
    with pytest.raises(TypeError, match="DatabaseConnectionPool"):
        DatabaseQuerySource(
            pool=object(),  # type: ignore[arg-type]
            query="SELECT 1",
            _config=KnotConfig(id="q"),
        )


def test_construct_rejects_empty_query(pool: SqlitePool) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        DatabaseQuerySource(
            pool=pool,
            query="",
            _config=KnotConfig(id="q"),
        )
