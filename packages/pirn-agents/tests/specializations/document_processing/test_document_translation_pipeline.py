"""Tests for :class:`DocumentTranslationPipeline`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.document_processing.document_translation_pipeline import (
    DocumentTranslationPipeline,
)
from pirn.tapestry import Tapestry

from tests.specializations.conftest import (
    StubLLMProvider,
)


def _make_knot(llm: StubLLMProvider) -> DocumentTranslationPipeline:
    with Tapestry():
        return DocumentTranslationPipeline(
            source="/tmp/placeholder.txt",
            target_language="French",
            llm=llm,
            _config=KnotConfig(id="translate"),
        )


class TestDocumentTranslationPipelineProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_target_language(self) -> None:
        llm = StubLLMProvider(["bonjour"])
        k = _make_knot(llm)
        with self.assertRaisesRegex(TypeError, "target_language"):
            await k.process(source="/tmp/x.txt", target_language="", llm=llm)

    async def test_translates_each_chunk(self) -> None:
        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        tmp_path = Path(_td.name)
        document = tmp_path / "doc.txt"
        document.write_text("hello world goodbye", encoding="utf-8")
        llm = StubLLMProvider(
            [
                "bonjour ",
                "monde adieu",
            ]
        )
        with Tapestry() as t:
            DocumentTranslationPipeline(
                source=str(document),
                target_language="French",
                llm=llm,
                chunk_size=11,
                _config=KnotConfig(id="translate"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        translation = result.outputs["translate"]
        assert translation == "bonjour monde adieu"
        # 2 chunks of size 11 from a 19-char doc → 2 LLM calls.
        assert len(llm.calls) == 2
