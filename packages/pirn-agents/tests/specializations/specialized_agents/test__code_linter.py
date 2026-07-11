"""Unit tests for :class:`_CodeLinter`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.specialized_agents._code_linter import (
    _CodeLinter,
)


class _CodeSource(Knot):
    def __init__(self, code, *, _config, **kwargs):
        self._code = code
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return self._code


class TestCodeLinterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_no_warnings_for_valid_python(self) -> None:
        code = "def hello():\n    return 'hello'"
        with Tapestry() as t:
            src = _CodeSource(code, _config=KnotConfig(id="src"))
            _CodeLinter(code=src, language="python", _config=KnotConfig(id="cl"))
        result = await t.run(RunRequest())
        assert result.outputs["cl"] == []

    async def test_warns_on_empty_code(self) -> None:
        with Tapestry() as t:
            src = _CodeSource("   ", _config=KnotConfig(id="src"))
            _CodeLinter(code=src, language="python", _config=KnotConfig(id="cl"))
        result = await t.run(RunRequest())
        warnings = result.outputs["cl"]
        assert any("empty" in w for w in warnings)

    async def test_warns_on_markdown_fences(self) -> None:
        code = "```python\ndef f(): pass\n```"
        with Tapestry() as t:
            src = _CodeSource(code, _config=KnotConfig(id="src"))
            _CodeLinter(code=src, language="python", _config=KnotConfig(id="cl"))
        result = await t.run(RunRequest())
        warnings = result.outputs["cl"]
        assert any("markdown" in w for w in warnings)

    async def test_warns_on_python_syntax_error(self) -> None:
        code = "def broken(\n    pass"
        with Tapestry() as t:
            src = _CodeSource(code, _config=KnotConfig(id="src"))
            _CodeLinter(code=src, language="python", _config=KnotConfig(id="cl"))
        result = await t.run(RunRequest())
        warnings = result.outputs["cl"]
        assert any("syntax" in w for w in warnings)

    async def test_no_python_parse_for_other_language(self) -> None:
        code = "function brokenJS( { return 1; }"  # invalid python but JS
        with Tapestry() as t:
            src = _CodeSource(code, _config=KnotConfig(id="src"))
            _CodeLinter(code=src, language="javascript", _config=KnotConfig(id="cl"))
        result = await t.run(RunRequest())
        # no syntax warning since language != python
        assert all("syntax" not in w for w in result.outputs["cl"])


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_empty_list_for_valid_python(self) -> None:
        with Tapestry():
            k = _CodeLinter.__new__(_CodeLinter)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        result = await k.process(code="def f(): return 1", language="python")
        assert result == []

    async def test_process_returns_warning_for_empty_code(self) -> None:
        with Tapestry():
            k = _CodeLinter.__new__(_CodeLinter)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        result = await k.process(code="", language="python")
        assert any("empty" in w for w in result)
