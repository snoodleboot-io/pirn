"""Tests for :class:`DocumentTranslationPipeline`."""

from __future__ import annotations

from pathlib import Path
import unittest
import tempfile


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing.document_translation_pipeline import (  # noqa: E501
    DocumentTranslationPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
)


class TestDocumentTranslationPipelineConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_target_language(self) -> None:
        llm = StubLLMProvider(["bonjour"])
        with self.assertRaisesRegex(TypeError, "target_language"):
            with Tapestry():
                DocumentTranslationPipeline(
                    source="/tmp/x.txt",
                    target_language="",
                    llm=llm,
                    _config=KnotConfig(id="translate"),
                )

    async def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            with Tapestry():
                DocumentTranslationPipeline(
                    source="/tmp/x.txt",
                    target_language="French",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="translate"),
                )


class TestDocumentTranslationPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_translates_each_chunk(self) -> None:
        _td_test_translates_each_chunk = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_translates_each_chunk.cleanup)
        tmp_path = Path(_td_test_translates_each_chunk.name)
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
