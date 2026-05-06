"""Unit tests for :class:`_CodeResponseFormatter`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.specialized_agents._code_response_formatter import (
    _CodeResponseFormatter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


class _Src(Knot):
    def __init__(self, value, *, _config, **kwargs):
        self._value = value
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return self._value


class TestCodeResponseFormatterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_wraps_code_in_agent_response(self) -> None:
        with Tapestry() as t:
            code_src = _Src("def f(): pass", _config=KnotConfig(id="cs"))
            warn_src = _Src([], _config=KnotConfig(id="ws"))
            _CodeResponseFormatter(
                code=code_src,
                warnings=warn_src,
                _config=KnotConfig(id="crf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["crf"]
        assert isinstance(out, AgentResponse)
        assert out.content == "def f(): pass"
        assert out.finish_reason == "stop"

    async def test_records_lint_warnings_count_in_usage(self) -> None:
        with Tapestry() as t:
            code_src = _Src("code", _config=KnotConfig(id="cs"))
            warn_src = _Src(["w1", "w2"], _config=KnotConfig(id="ws"))
            _CodeResponseFormatter(
                code=code_src,
                warnings=warn_src,
                _config=KnotConfig(id="crf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["crf"]
        assert out.usage["lint_warnings"] == 2


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_agent_response_with_code(self) -> None:
        with Tapestry():
            k = _CodeResponseFormatter.__new__(_CodeResponseFormatter)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        result = await k.process(code="def f(): pass", warnings=[])
        assert isinstance(result, AgentResponse)
        assert result.content == "def f(): pass"
        assert result.usage["lint_warnings"] == 0

    async def test_process_records_warning_count(self) -> None:
        with Tapestry():
            k = _CodeResponseFormatter.__new__(_CodeResponseFormatter)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        result = await k.process(code="code", warnings=["w1", "w2", "w3"])
        assert result.usage["lint_warnings"] == 3
