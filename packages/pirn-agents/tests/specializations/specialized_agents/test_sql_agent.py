"""Tests for :class:`SQLAgent`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.specialized_agents.sql_agent import (
    SQLAgent,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

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
