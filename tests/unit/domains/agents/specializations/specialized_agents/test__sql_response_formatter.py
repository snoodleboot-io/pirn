"""Unit tests for :class:`_SQLResponseFormatter`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.specialized_agents._sql_response_formatter import (
    _SQLResponseFormatter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


class _Src(Knot):
    def __init__(self, value, *, _config, **kwargs):
        self._value = value
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return self._value


class TestSQLResponseFormatterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_formats_sql_and_rows(self) -> None:
        with Tapestry() as t:
            sql_src = _Src("SELECT * FROM t", _config=KnotConfig(id="ss"))
            rows_src = _Src([(1, "Alice")], _config=KnotConfig(id="rs"))
            _SQLResponseFormatter(
                sql=sql_src,
                rows=rows_src,
                _config=KnotConfig(id="srf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["srf"]
        assert isinstance(out, AgentResponse)
        assert "SELECT * FROM t" in out.content
        assert "Rows (1)" in out.content
        assert out.finish_reason == "stop"

    async def test_zero_rows_included(self) -> None:
        with Tapestry() as t:
            sql_src = _Src("SELECT 1", _config=KnotConfig(id="ss"))
            rows_src = _Src([], _config=KnotConfig(id="rs"))
            _SQLResponseFormatter(
                sql=sql_src,
                rows=rows_src,
                _config=KnotConfig(id="srf"),
            )
        result = await t.run(RunRequest())
        assert "Rows (0)" in result.outputs["srf"].content


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_agent_response_with_sql_and_rows(self) -> None:
        with Tapestry():
            k = _SQLResponseFormatter.__new__(_SQLResponseFormatter)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        result = await k.process(sql="SELECT 1", rows=[(42,)])
        assert isinstance(result, AgentResponse)
        assert "SELECT 1" in result.content
        assert "Rows (1)" in result.content
