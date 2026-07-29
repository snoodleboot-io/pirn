"""Characterisation tests for the system-prompt layer-kind vocabulary.

Pins the canonical composition order (persona, policy, tools, memory) and the
"unknown kind sorts last, first-seen order preserved" fallback so moving the
inline rank map onto :class:`SystemPromptKind` is behaviour-preserving.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.prompt.system_prompt_composer import SystemPromptComposer
from pirn_agents.prompt.system_prompt_kind import SystemPromptKind
from pirn_agents.prompt.system_prompt_layer import SystemPromptLayer


@knot
async def _empty_layers() -> tuple:
    """Upstream stand-in supplying the composer's ``layers`` port."""
    return ()


def _make_knot() -> SystemPromptComposer:
    with Tapestry():
        upstream = _empty_layers(_config=KnotConfig(id="l"))
        return SystemPromptComposer(layers=upstream, _config=KnotConfig(id="compose"))


class TestCanonicalRankVocabulary(unittest.IsolatedAsyncioTestCase):
    async def test_canonical_kinds_order_by_rank_not_input_order(self) -> None:
        # Arrange: every canonical kind supplied in reverse rank order.
        composer = _make_knot()
        layers = (
            SystemPromptLayer(kind="memory", content="M"),
            SystemPromptLayer(kind="tools", content="T"),
            SystemPromptLayer(kind="policy", content="P"),
            SystemPromptLayer(kind="persona", content="X"),
        )

        # Act
        out = await composer.process(layers=layers)

        # Assert: persona → policy → tools → memory.
        assert out == "X\n\nP\n\nT\n\nM"

    async def test_unknown_kinds_share_the_trailing_rank(self) -> None:
        # Arrange: two custom kinds bracketing a canonical one.
        composer = _make_knot()
        layers = (
            SystemPromptLayer(kind="zebra", content="Z"),
            SystemPromptLayer(kind="memory", content="M"),
            SystemPromptLayer(kind="aardvark", content="A"),
        )

        # Act
        out = await composer.process(layers=layers)

        # Assert: memory (rank 3) precedes both customs, which keep first-seen order.
        assert out == "M\n\nZ\n\nA"

    async def test_free_form_custom_kinds_still_compose(self) -> None:
        # Arrange / Act / Assert: a non-vocabulary kind is not rejected.
        composer = _make_knot()
        layers = (SystemPromptLayer(kind="scratchpad", content="S"),)
        assert await composer.process(layers=layers) == "S"

    async def test_equal_canonical_ranks_keep_first_seen_order(self) -> None:
        # Arrange / Act / Assert: two layers of the same kind keep input order.
        composer = _make_knot()
        layers = (
            SystemPromptLayer(kind="tools", content="T1"),
            SystemPromptLayer(kind="tools", content="T2"),
        )
        assert await composer.process(layers=layers) == "T1\n\nT2"


class TestSystemPromptKindEnum(unittest.TestCase):
    def test_values_are_plain_strings(self) -> None:
        # Arrange / Act / Assert: the str mixin keeps `==` against raw literals working,
        # so a layer declared with a bare string still matches the vocabulary.
        assert SystemPromptKind.PERSONA == "persona"
        assert SystemPromptKind.POLICY == "policy"
        assert SystemPromptKind.TOOLS == "tools"
        assert SystemPromptKind.MEMORY == "memory"

    def test_declaration_order_is_the_composition_order(self) -> None:
        # Arrange / Act / Assert
        assert [member.value for member in SystemPromptKind] == [
            "persona",
            "policy",
            "tools",
            "memory",
        ]

    def test_rank_of_matches_the_historical_rank_map(self) -> None:
        # Arrange / Act / Assert: byte-identical to the replaced {"persona": 0, ...} dict.
        assert SystemPromptKind.rank_of("persona") == 0
        assert SystemPromptKind.rank_of("policy") == 1
        assert SystemPromptKind.rank_of("tools") == 2
        assert SystemPromptKind.rank_of("memory") == 3

    def test_rank_of_unknown_kind_is_the_trailing_rank(self) -> None:
        # Arrange / Act / Assert: the historical `.get(kind, 4)` fallback.
        assert SystemPromptKind.rank_of("custom") == 4
        assert SystemPromptKind.rank_of("") == 4
        assert SystemPromptKind.rank_of("PERSONA") == 4

    def test_rank_of_accepts_a_member_as_well_as_its_value(self) -> None:
        # Arrange / Act / Assert: callers may pass the enum itself.
        assert SystemPromptKind.rank_of(SystemPromptKind.TOOLS) == 2


if __name__ == "__main__":
    unittest.main()
