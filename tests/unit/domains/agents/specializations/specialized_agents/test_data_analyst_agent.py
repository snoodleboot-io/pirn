"""Tests for :class:`DataAnalystAgent`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.specialized_agents.data_analyst_agent import (  # noqa: E501
    DataAnalystAgent,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubDatabaseConnectionPool,
    StubLLMProvider,
)


class TestDataAnalystAgentConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        llm = StubLLMProvider(["SELECT 1", "Looks fine."])
        with self.assertRaisesRegex(TypeError, "pool must be a DatabaseConnectionPool"):
            with Tapestry():
                DataAnalystAgent(
                    question="how many users?",
                    llm=llm,
                    pool="not-a-pool",  # type: ignore[arg-type]
                    _config=KnotConfig(id="analyst"),
                )

    async def test_rejects_non_string_schema(self) -> None:
        llm = StubLLMProvider(["SELECT 1", "ok"])
        pool = StubDatabaseConnectionPool()
        with self.assertRaisesRegex(TypeError, "schema_description"):
            with Tapestry():
                DataAnalystAgent(
                    question="?",
                    llm=llm,
                    pool=pool,
                    schema_description=123,  # type: ignore[arg-type]
                    _config=KnotConfig(id="analyst"),
                )


class TestDataAnalystAgentHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_runs_sql_then_writes_analysis(self) -> None:
        llm = StubLLMProvider(
            [
                "SELECT count(*) FROM users",
                "There are 7 users; growth is steady.",
            ]
        )
        pool = StubDatabaseConnectionPool(rows=[(7,)])
        with Tapestry() as t:
            DataAnalystAgent(
                question="how many users do we have?",
                llm=llm,
                pool=pool,
                schema_description="users(id, name)",
                _config=KnotConfig(id="analyst"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["analyst"]
        assert isinstance(response, AgentResponse)
        assert "SQL:" in response.content
        assert "Analysis:" in response.content
        assert "7 users" in response.content
        assert pool.queries == ["SELECT count(*) FROM users"]
