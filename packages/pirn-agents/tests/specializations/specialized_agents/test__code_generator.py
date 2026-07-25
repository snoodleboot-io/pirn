"""Unit tests for :class:`_CodeGenerator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.specialized_agents._code_generator import (
    _CodeGenerator,
)
from tests.specializations.conftest import StubLLMProvider


class TestCodeGeneratorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_llm_generated_code(self) -> None:
        llm = StubLLMProvider(["def add(a, b):\n    return a + b"])
        with Tapestry() as t:
            _CodeGenerator(
                task="Write an add function",
                llm=llm,
                language="python",
                _config=KnotConfig(id="cg"),
            )
        result = await t.run(RunRequest())
        assert "def add" in result.outputs["cg"]

    async def test_language_in_system_prompt(self) -> None:
        llm = StubLLMProvider(["int add(int a, int b) { return a + b; }"])
        with Tapestry() as t:
            _CodeGenerator(
                task="write add function",
                llm=llm,
                language="C++",
                _config=KnotConfig(id="cg"),
            )
        await t.run(RunRequest())
        system_msg = llm.calls[0][0]["content"]
        assert "C++" in system_msg

    async def test_rejects_empty_task(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry() as t:
            _CodeGenerator(
                task="",
                llm=llm,
                language="python",
                _config=KnotConfig(id="cg"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_empty_task(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            k = _CodeGenerator.__new__(_CodeGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(task="", llm=llm, language="python")
