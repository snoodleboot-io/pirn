"""Unit tests for :class:`_SQLGenerator`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.specialized_agents._sql_generator import (
    _SQLGenerator,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestSQLGeneratorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_sql_from_llm(self) -> None:
        llm = StubLLMProvider(["SELECT COUNT(*) FROM users"])
        with Tapestry() as t:
            _SQLGenerator(
                question="How many users?",
                llm=llm,
                schema_description="users(id, name)",
                _config=KnotConfig(id="sg"),
            )
        result = await t.run(RunRequest())
        sql = result.outputs["sg"]
        assert "SELECT" in sql

    async def test_schema_description_in_system_prompt(self) -> None:
        llm = StubLLMProvider(["SELECT 1"])
        with Tapestry() as t:
            _SQLGenerator(
                question="query?",
                llm=llm,
                schema_description="orders(id, amount, date)",
                _config=KnotConfig(id="sg"),
            )
        await t.run(RunRequest())
        system_msg = llm.calls[0][0]["content"]
        assert "orders(id, amount, date)" in system_msg

    async def test_rejects_empty_question(self) -> None:
        llm = StubLLMProvider(["SELECT 1"])
        with Tapestry() as t:
            _SQLGenerator(
                question="",
                llm=llm,
                schema_description="",
                _config=KnotConfig(id="sg"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
