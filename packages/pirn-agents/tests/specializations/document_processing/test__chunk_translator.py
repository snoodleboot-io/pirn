"""Unit tests for :class:`ChunkTranslator`.

PIR-867: chunk translations are independent of each other, so
``ChunkTranslator`` fans them out (one ``ChunkTranslation`` knot per chunk
wired into an ``Aggregator``) rather than awaiting ``llm.chat`` in a
hand-rolled ``for`` loop. ``process`` therefore returns the sink of an inner
pipeline instead of the translated string directly, so the outcome tests run
a real tapestry and read the translator's output (the pattern PIR-856
established for ``ParallelToolCaller``). Because the chunks now execute
concurrently, ``_KeyedLLMProvider`` scripts a response *per input chunk*
rather than by call order — a call-order script would be flaky under
concurrent dispatch and would not actually be testing the concatenation
order guarantee.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.document_processing._chunk_translator import (
    ChunkTranslator,
)


class _KeyedLLMProvider(LLMProvider):
    """Scripted LLM provider keyed by the user message content.

    Unlike a call-order script, this is safe under concurrent dispatch: each
    call's response depends only on what it was asked to translate, never on
    which sibling call happened to run first.
    """

    def __init__(self, translations: Mapping[str, str]) -> None:
        self._translations = translations
        self.calls: list[Sequence[Mapping[str, Any]]] = []

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        self.calls.append(list(messages))
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        return {"role": "assistant", "content": self._translations[user_content]}


def _run(llm: _KeyedLLMProvider, chunks: list[str], target_language: str) -> Any:
    with Tapestry() as t:
        ChunkTranslator(
            chunks=chunks,
            target_language=target_language,
            llm=llm,
            _config=KnotConfig(id="ct"),
        )
    return t


class TestChunkTranslatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_empty_string(self) -> None:
        llm = _KeyedLLMProvider({})
        t = _run(llm, [], "French")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert result.outputs["ct"] == ""

    async def test_single_chunk_translated(self) -> None:
        llm = _KeyedLLMProvider({"Hello": "Bonjour"})
        t = _run(llm, ["Hello"], "French")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert result.outputs["ct"] == "Bonjour"

    async def test_multiple_chunks_concatenated_in_order(self) -> None:
        llm = _KeyedLLMProvider({"One": "Un", "Two": "Deux"})
        t = _run(llm, ["One", "Two"], "French")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert result.outputs["ct"] == "UnDeux"

    async def test_llm_called_once_per_chunk(self) -> None:
        llm = _KeyedLLMProvider({"a": "x", "b": "y", "c": "z"})
        t = _run(llm, ["a", "b", "c"], "Spanish")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert len(llm.calls) == 3

    async def test_target_language_in_system_prompt(self) -> None:
        llm = _KeyedLLMProvider({"hello": "hola"})
        t = _run(llm, ["hello"], "Spanish")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        system_content = llm.calls[0][0]["content"]
        assert "Spanish" in system_content

    async def test_each_chunk_gets_its_own_lineage_row(self) -> None:
        """PIR-867: each chunk is a node now, not an inline await in a for loop."""
        llm = _KeyedLLMProvider({"a": "x", "b": "y"})
        t = _run(llm, ["a", "b"], "Spanish")
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        children = await t.history.children_of(result.run_id)
        inner_knot_ids = {row.knot_id for child in children for row in child.lineage}
        assert {"translate_0", "translate_1"} <= inner_knot_ids, inner_knot_ids


if __name__ == "__main__":
    unittest.main()
