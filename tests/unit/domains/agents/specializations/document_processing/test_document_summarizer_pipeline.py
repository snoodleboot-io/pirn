"""Tests for :class:`DocumentSummarizerPipeline`."""

from __future__ import annotations

from pathlib import Path

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.document_processing.document_summarizer_pipeline import (  # noqa: E501
    DocumentSummarizerPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
)


@pytest.mark.asyncio
class TestDocumentSummarizerPipelineConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                DocumentSummarizerPipeline(
                    source="/tmp/x.txt",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="summ"),
                )

    async def test_rejects_zero_chunk_size(self) -> None:
        llm = StubLLMProvider(["summary"])
        with pytest.raises(ValueError, match="chunk_size"):
            with Tapestry():
                DocumentSummarizerPipeline(
                    source="/tmp/x.txt",
                    llm=llm,
                    chunk_size=0,
                    _config=KnotConfig(id="summ"),
                )


@pytest.mark.asyncio
class TestDocumentSummarizerPipelineHappyPath:
    async def test_returns_reduced_summary(self, tmp_path: Path) -> None:
        document = tmp_path / "doc.txt"
        document.write_text("alpha beta gamma delta epsilon", encoding="utf-8")
        llm = StubLLMProvider(
            [
                "chunk-1 summary",
                "chunk-2 summary",
                "combined summary",
            ]
        )
        with Tapestry() as t:
            DocumentSummarizerPipeline(
                source=str(document),
                llm=llm,
                chunk_size=15,
                _config=KnotConfig(id="summ"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        summary = result.outputs["summ"]
        assert summary == "combined summary"
        # 2 map calls + 1 reduce call.
        assert len(llm.calls) == 3
