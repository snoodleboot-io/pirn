"""Unit tests for :class:`MetadataExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.document_processing.metadata_extractor import (
    MetadataExtractor,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> MetadataExtractor:
    with Tapestry():
        return MetadataExtractor(
            document="sample",
            llm=llm,
            _config=KnotConfig(id="me"),
        )


class TestMetadataExtractorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_json_metadata(self) -> None:
        json_reply = '{"title": "My Doc", "author": "Alice", "date": "2024-01-01", "summary": "Good"}'
        llm = StubLLMProvider([json_reply])
        k = _make_knot(llm)
        meta = await k.process(document="sample document content", llm=llm)
        assert meta["title"] == "My Doc"
        assert meta["author"] == "Alice"

    async def test_missing_fields_return_none(self) -> None:
        llm = StubLLMProvider(["{}"])
        k = _make_knot(llm)
        meta = await k.process(document="some doc", llm=llm)
        assert meta["title"] is None
        assert meta["author"] is None

    async def test_rejects_non_string_document(self) -> None:
        llm = StubLLMProvider(["{}"])
        k = _make_knot(llm)
        with self.assertRaises(TypeError):
            await k.process(document=42, llm=llm)  # type: ignore[arg-type]

    async def test_handles_json_embedded_in_prose(self) -> None:
        reply = 'Here is your answer: {"title": "X", "author": null, "date": null, "summary": null}'
        llm = StubLLMProvider([reply])
        k = _make_knot(llm)
        meta = await k.process(document="text", llm=llm)
        assert meta["title"] == "X"
