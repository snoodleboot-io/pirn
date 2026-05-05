"""Unit tests for :class:`MetadataExtractor`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing.metadata_extractor import (
    MetadataExtractor,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestMetadataExtractorConstruction(unittest.TestCase):
    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                MetadataExtractor(
                    document="hello",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="me"),
                )


class TestMetadataExtractorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_json_metadata(self) -> None:
        json_reply = '{"title": "My Doc", "author": "Alice", "date": "2024-01-01", "summary": "Good"}'
        llm = StubLLMProvider([json_reply])
        with Tapestry() as t:
            MetadataExtractor(
                document="sample document content",
                llm=llm,
                _config=KnotConfig(id="me"),
            )
        result = await t.run(RunRequest())
        meta = result.outputs["me"]
        assert meta["title"] == "My Doc"
        assert meta["author"] == "Alice"

    async def test_missing_fields_return_none(self) -> None:
        llm = StubLLMProvider(["{}"])
        with Tapestry() as t:
            MetadataExtractor(
                document="some doc",
                llm=llm,
                _config=KnotConfig(id="me"),
            )
        result = await t.run(RunRequest())
        meta = result.outputs["me"]
        assert meta["title"] is None
        assert meta["author"] is None

    async def test_rejects_non_string_document(self) -> None:
        llm = StubLLMProvider(["{}"])
        with Tapestry():
            with self.assertRaises(TypeError):
                MetadataExtractor(
                    document=42,  # type: ignore[arg-type]
                    llm=llm,
                    _config=KnotConfig(id="me"),
                )

    async def test_handles_json_embedded_in_prose(self) -> None:
        reply = 'Here is your answer: {"title": "X", "author": null, "date": null, "summary": null}'
        llm = StubLLMProvider([reply])
        with Tapestry() as t:
            MetadataExtractor(
                document="text",
                llm=llm,
                _config=KnotConfig(id="me"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["me"]["title"] == "X"
