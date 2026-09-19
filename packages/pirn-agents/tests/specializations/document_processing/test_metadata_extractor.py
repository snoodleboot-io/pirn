"""Unit tests for :class:`MetadataExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.exceptions.llm_response_parse_error import LLMResponseParseError
from pirn_agents.specializations.document_processing.metadata_extractor import (
    MetadataExtractor,
)
from tests.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> MetadataExtractor:
    with Tapestry():
        return MetadataExtractor(
            document="sample",
            llm=llm,
            _config=KnotConfig(id="me"),
        )


class TestMetadataExtractorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_json_metadata(self) -> None:
        json_reply = (
            '{"title": "My Doc", "author": "Alice", "date": "2024-01-01", "summary": "Good"}'
        )
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
        result = await k({"document": 42, "llm": llm})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_handles_json_embedded_in_prose(self) -> None:
        reply = 'Here is your answer: {"title": "X", "author": null, "date": null, "summary": null}'
        llm = StubLLMProvider([reply])
        k = _make_knot(llm)
        meta = await k.process(document="text", llm=llm)
        assert meta["title"] == "X"


class TestMetadataExtractorRefusesUnparseableReplies(unittest.IsolatedAsyncioTestCase):
    """An unreadable reply is a failed turn, not a document with no metadata.

    Before PIR-873 ``_parse_json`` swallowed every parse failure and returned
    ``{}``, so ``process`` handed back four ``None`` fields — exactly what a
    successful extraction of an anonymous document looks like. Callers could
    not tell the two apart.
    """

    async def test_prose_with_no_json_raises(self) -> None:
        llm = StubLLMProvider(["I could not find any metadata in that document."])
        knot = _make_knot(llm)
        with self.assertRaises(LLMResponseParseError):
            await knot.process(document="text", llm=llm)

    async def test_malformed_json_object_raises(self) -> None:
        llm = StubLLMProvider(['{"title": "X", "author": }'])
        knot = _make_knot(llm)
        with self.assertRaises(LLMResponseParseError):
            await knot.process(document="text", llm=llm)

    async def test_json_array_reply_raises(self) -> None:
        llm = StubLLMProvider(['["title", "author"]'])
        knot = _make_knot(llm)
        with self.assertRaises(LLMResponseParseError):
            await knot.process(document="text", llm=llm)

    async def test_the_raw_reply_is_carried_on_the_error(self) -> None:
        llm = StubLLMProvider(["no json here"])
        knot = _make_knot(llm)
        with self.assertRaises(LLMResponseParseError) as caught:
            await knot.process(document="text", llm=llm)
        assert caught.exception.reply == "no json here"

    async def test_a_failed_parse_surfaces_as_an_engine_error(self) -> None:
        llm = StubLLMProvider(["nothing structured at all"])
        knot = _make_knot(llm)
        outcome = await knot({"document": "text", "llm": llm})
        assert isinstance(outcome, Err)
        assert outcome.record.exc_type == "LLMResponseParseError"
