"""Unit tests for :class:`PromptRenderKnot`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.prompt.prompt_render_error import PromptRenderError
from pirn_agents.prompt.prompt_render_knot import PromptRenderKnot
from pirn_agents.prompt.prompt_template import PromptTemplate


def _make_knot() -> PromptRenderKnot:
    @knot
    async def _t() -> PromptTemplate:
        return PromptTemplate(name="greet", version="1.0.0", template="Hi {{ name }}!")

    with Tapestry():
        upstream = _t(_config=KnotConfig(id="t"))
        return PromptRenderKnot(template=upstream, _config=KnotConfig(id="render"))


_TEMPLATE = PromptTemplate(name="greet", version="1.0.0", template="Hi {{ name }}!")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_renders_template(self) -> None:
        k = _make_knot()
        out = await k.process(template=_TEMPLATE, variables={"name": "Ada"})
        assert out == "Hi Ada!"

    async def test_rejects_non_template(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "template"):
            await k.process(template="nope", variables={})  # type: ignore[arg-type]

    async def test_rejects_non_mapping_variables(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "variables"):
            await k.process(template=_TEMPLATE, variables=["x"])  # type: ignore[arg-type]

    async def test_strict_missing_variable_raises(self) -> None:
        k = _make_knot()
        with self.assertRaises(PromptRenderError):
            await k.process(template=_TEMPLATE, variables={}, strict=True)

    async def test_non_strict_leaves_placeholder(self) -> None:
        k = _make_knot()
        out = await k.process(template=_TEMPLATE, variables={}, strict=False)
        assert out == "Hi {{ name }}!"


if __name__ == "__main__":
    unittest.main()
