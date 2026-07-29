"""Unit tests for :class:`SystemPromptComposer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.prompt.system_prompt_composer import SystemPromptComposer
from pirn_agents.prompt.system_prompt_layer import SystemPromptLayer


def _make_knot() -> SystemPromptComposer:
    @knot
    async def _l() -> tuple:
        return ()

    with Tapestry():
        upstream = _l(_config=KnotConfig(id="l"))
        return SystemPromptComposer(layers=upstream, _config=KnotConfig(id="compose"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_composes_in_canonical_order_regardless_of_input_order(self) -> None:
        k = _make_knot()
        layers = (
            SystemPromptLayer(kind="memory", content="MEM"),
            SystemPromptLayer(kind="persona", content="YOU ARE"),
            SystemPromptLayer(kind="tools", content="TOOLS"),
            SystemPromptLayer(kind="policy", content="POLICY"),
        )
        out = await k.process(layers=layers)
        assert out == "YOU ARE\n\nPOLICY\n\nTOOLS\n\nMEM"

    async def test_custom_layers_come_after_canonical_in_first_seen_order(self) -> None:
        k = _make_knot()
        layers = (
            SystemPromptLayer(kind="extra_b", content="B"),
            SystemPromptLayer(kind="persona", content="P"),
            SystemPromptLayer(kind="extra_a", content="A"),
        )
        out = await k.process(layers=layers)
        assert out == "P\n\nB\n\nA"

    async def test_empty_layers_are_skipped(self) -> None:
        k = _make_knot()
        layers = (
            SystemPromptLayer(kind="persona", content="P"),
            SystemPromptLayer(kind="policy", content="   "),
            SystemPromptLayer(kind="tools", content=""),
        )
        out = await k.process(layers=layers)
        assert out == "P"

    async def test_all_empty_yields_empty_string(self) -> None:
        k = _make_knot()
        layers = (SystemPromptLayer(kind="persona", content=""),)
        assert await k.process(layers=layers) == ""

    async def test_title_is_rendered_above_content(self) -> None:
        k = _make_knot()
        layers = (SystemPromptLayer(kind="tools", content="calc", title="# Tools"),)
        assert await k.process(layers=layers) == "# Tools\ncalc"

    async def test_custom_separator(self) -> None:
        k = _make_knot()
        layers = (
            SystemPromptLayer(kind="persona", content="P"),
            SystemPromptLayer(kind="policy", content="Q"),
        )
        assert await k.process(layers=layers, separator=" | ") == "P | Q"

    async def test_rejects_non_sequence_layers(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "layers"):
            await k.process(layers=42)  # type: ignore[arg-type]

    async def test_rejects_non_layer_element(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "layers\\[0\\]"):
            await k.process(layers=("nope",))  # type: ignore[arg-type]

    async def test_rejects_non_str_separator(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "separator"):
            await k.process(layers=(), separator=5)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
