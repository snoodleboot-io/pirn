"""Unit tests for :class:`_ChunkTranslator`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing._chunk_translator import (
    _ChunkTranslator,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestChunkTranslatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_empty_chunks_returns_empty_string(self) -> None:
        llm = StubLLMProvider([])
        with Tapestry() as t:
            _ChunkTranslator(
                chunks=[],
                target_language="French",
                llm=llm,
                _config=KnotConfig(id="ct"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ct"] == ""

    async def test_single_chunk_translated(self) -> None:
        llm = StubLLMProvider(["Bonjour"])
        with Tapestry() as t:
            _ChunkTranslator(
                chunks=["Hello"],
                target_language="French",
                llm=llm,
                _config=KnotConfig(id="ct"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ct"] == "Bonjour"

    async def test_multiple_chunks_concatenated(self) -> None:
        llm = StubLLMProvider(["Un", "Deux"])
        with Tapestry() as t:
            _ChunkTranslator(
                chunks=["One", "Two"],
                target_language="French",
                llm=llm,
                _config=KnotConfig(id="ct"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ct"] == "UnDeux"

    async def test_llm_called_once_per_chunk(self) -> None:
        llm = StubLLMProvider(["x", "y", "z"])
        with Tapestry() as t:
            _ChunkTranslator(
                chunks=["a", "b", "c"],
                target_language="Spanish",
                llm=llm,
                _config=KnotConfig(id="ct"),
            )
        await t.run(RunRequest())
        assert len(llm.calls) == 3

    async def test_target_language_in_system_prompt(self) -> None:
        llm = StubLLMProvider(["hola"])
        with Tapestry() as t:
            _ChunkTranslator(
                chunks=["hello"],
                target_language="Spanish",
                llm=llm,
                _config=KnotConfig(id="ct"),
            )
        await t.run(RunRequest())
        system_content = llm.calls[0][0]["content"]
        assert "Spanish" in system_content
