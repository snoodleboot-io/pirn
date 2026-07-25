"""Mirrored tests for :class:`PromptPrefixOrderer` stable-prefix ordering (PIR-510).

Asserts the stable prefix is byte-identical across repeated builds with differing
variable content, and that reordering preserves every segment's content.
"""

from __future__ import annotations

import pytest

from pirn_agents.caching.prompt_prefix_orderer import PromptPrefixOrderer
from pirn_agents.caching.prompt_segment import PromptSegment


def _segments(user_text: str) -> list[PromptSegment]:
    """A realistic prompt: variable user turn authored between stable segments."""
    return [
        PromptSegment(kind="system", content="You are helpful.", stable=True),
        PromptSegment(kind="user", content=user_text, stable=False),
        PromptSegment(kind="tools", content="[tool schemas]", stable=True),
    ]


class TestValidation:
    def test_bad_separator_rejected(self) -> None:
        with pytest.raises(TypeError, match="separator"):
            PromptPrefixOrderer(separator=123)  # type: ignore[arg-type]

    def test_non_segment_rejected(self) -> None:
        with pytest.raises(TypeError, match="PromptSegment"):
            PromptPrefixOrderer().order(["nope"])  # type: ignore[list-item]


class TestOrdering:
    def test_stable_segments_hoisted_before_variable(self) -> None:
        ordered = PromptPrefixOrderer().order(_segments("hi"))
        kinds = [s.kind for s in ordered]
        assert kinds == ["system", "tools", "user"]  # stable first, order preserved

    def test_relative_order_preserved_within_groups(self) -> None:
        segs = [
            PromptSegment(kind="policy", content="P", stable=True),
            PromptSegment(kind="ctx-a", content="A", stable=False),
            PromptSegment(kind="persona", content="Persona", stable=True),
            PromptSegment(kind="ctx-b", content="B", stable=False),
        ]
        ordered = PromptPrefixOrderer().order(segs)
        assert [s.kind for s in ordered] == ["policy", "persona", "ctx-a", "ctx-b"]

    def test_no_content_lost_or_rewritten(self) -> None:
        segs = _segments("question?")
        ordered = PromptPrefixOrderer().order(segs)
        assert {s.content for s in ordered} == {s.content for s in segs}


class TestStablePrefix:
    def test_prefix_identical_across_variable_content(self) -> None:
        orderer = PromptPrefixOrderer()
        first = orderer.stable_prefix(_segments("first question"))
        second = orderer.stable_prefix(_segments("a totally different question"))
        assert first == second  # cacheable prefix unaffected by the user turn

    def test_prefix_excludes_variable_content(self) -> None:
        prefix = PromptPrefixOrderer().stable_prefix(_segments("secret user text"))
        assert "secret user text" not in prefix
        assert "You are helpful." in prefix
        assert "[tool schemas]" in prefix

    def test_build_places_prefix_first(self) -> None:
        built = PromptPrefixOrderer(separator="|").build(_segments("Q"))
        assert built == "You are helpful.|[tool schemas]|Q"

    def test_prefix_is_repeatable(self) -> None:
        orderer = PromptPrefixOrderer()
        segs = _segments("x")
        assert orderer.stable_prefix(segs) == orderer.stable_prefix(segs)
