"""Tests for :class:`SQLAgent`."""

from __future__ import annotations

import sqlite3
import unittest
from typing import Any

import pytest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.specialized_agents.sql_agent import (
    SQLAgent,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import (
    StubDatabaseConnectionPool,
    StubLLMProvider,
)


class TestSQLAgentProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        pool = StubDatabaseConnectionPool()
        llm = StubLLMProvider(["SELECT 1"])
        agent = SQLAgent(
            question="who?",
            llm=llm,
            pool=pool,
            _config=KnotConfig(id="sql"),
        )
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await agent.process(question="who?", llm="not-a-provider", pool=pool)  # type: ignore[arg-type]

    async def test_rejects_non_pool(self) -> None:
        llm = StubLLMProvider(["SELECT 1"])
        pool = StubDatabaseConnectionPool()
        agent = SQLAgent(
            question="who?",
            llm=llm,
            pool=pool,
            _config=KnotConfig(id="sql"),
        )
        with self.assertRaisesRegex(TypeError, "pool must be a DatabaseConnectionPool"):
            await agent.process(question="who?", llm=llm, pool="not-a-pool")  # type: ignore[arg-type]


class TestSQLAgentHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_runs_sql_and_formats_response(self) -> None:
        llm = StubLLMProvider(["SELECT id, name FROM users WHERE id = ?"])
        pool = StubDatabaseConnectionPool(rows=[(1, "Ada")])
        with Tapestry() as t:
            SQLAgent(
                question="who is user 1?",
                llm=llm,
                pool=pool,
                schema_description="users(id, name)",
                _config=KnotConfig(id="sql"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["sql"]
        assert isinstance(response, AgentResponse)
        assert "SELECT id, name FROM users" in response.content
        assert "Ada" in response.content
        assert pool.queries == ["SELECT id, name FROM users WHERE id = ?"]


class TestSQLAgentSafety(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_inline_brace_interpolation(self) -> None:
        # The LLM emits SQL with a Python-format placeholder; the pool's
        # ``_reject_inline_interpolation`` guard must trip and the run must
        # fail rather than send the unsafe query downstream.
        llm = StubLLMProvider(["SELECT * FROM users WHERE id = {user_id}"])
        pool = StubDatabaseConnectionPool(rows=[])
        with Tapestry() as t:
            SQLAgent(
                question="give me users",
                llm=llm,
                pool=pool,
                _config=KnotConfig(id="sql"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
        assert pool.queries == []

    async def test_rejects_inline_printf_interpolation(self) -> None:
        llm = StubLLMProvider(["SELECT * FROM users WHERE id = %s"])
        pool = StubDatabaseConnectionPool(rows=[])
        with Tapestry() as t:
            SQLAgent(
                question="give me users",
                llm=llm,
                pool=pool,
                _config=KnotConfig(id="sql"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
        assert pool.queries == []


class TestSQLAgentIsReadOnlyByDefault(unittest.IsolatedAsyncioTestCase):
    """Regression (PIR-817): the agent executed whatever statement the model wrote.

    The inline-interpolation guard above stops the model *splicing values into*
    the statement; it never stopped the model choosing a destructive statement
    in the first place. These drive the whole agent, so they fail if the guard
    is dropped anywhere between :class:`SQLAgent` and the pool.
    """

    async def test_refuses_a_generated_drop_table(self) -> None:
        llm = StubLLMProvider(["DROP TABLE users"])
        pool = StubDatabaseConnectionPool(rows=[])
        with Tapestry() as t:
            SQLAgent(
                question="please clean up the users table",
                llm=llm,
                pool=pool,
                _config=KnotConfig(id="sql"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
        assert pool.queries == []

    async def test_refuses_a_generated_delete(self) -> None:
        llm = StubLLMProvider(["DELETE FROM users WHERE id = 1"])
        pool = StubDatabaseConnectionPool(rows=[])
        with Tapestry() as t:
            SQLAgent(
                question="remove user 1",
                llm=llm,
                pool=pool,
                _config=KnotConfig(id="sql"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
        assert pool.queries == []


class TestSQLAgentOptedInWriteIsDurable:
    """A write the operator opted into must actually persist (PIR-817).

    The defect had two halves and fixing only the guard would leave the second:
    a permitted write was routed through core's ``SqlitePool.fetch_all``, which
    — unlike its ``execute`` — never commits, so the write was discarded when
    the connection closed. This drives the whole agent against a real database
    file and reads the result back with plain ``sqlite3``.
    """

    async def test_a_generated_insert_survives_close_and_reopen(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "agent_write.db")

        setup = SqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        await setup.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        await setup.close()

        llm = StubLLMProvider(["INSERT INTO users (id, name) VALUES (1, 'Ada')"])
        pool = SqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        try:
            with Tapestry() as t:
                SQLAgent(
                    question="add Ada",
                    llm=llm,
                    pool=pool,
                    read_only=False,
                    _config=KnotConfig(id="sql"),
                )
            result = await t.run(RunRequest())
            assert result.succeeded, result.exceptions
        finally:
            await pool.close()

        with sqlite3.connect(database) as disk:
            assert disk.execute("SELECT id, name FROM users").fetchall() == [(1, "Ada")]
