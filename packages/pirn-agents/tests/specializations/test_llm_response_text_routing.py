"""Behaviour tests: every specialization knot reads LLM text through one extractor.

Seven knots under ``specializations/`` each carried a private ``_extract_text``
copy (PIR-873). Two of those copies were *narrower* than the shared
:class:`~pirn_agents.specializations.llm_response_text.LlmResponseText` — they
did not understand a provider that returns ``content`` as a list of text
blocks, and stringified the whole mapping instead. The rest were byte-identical
duplicates that drifted out of the shared implementation's reach.

``TestBlockListContentIsExtracted`` pins the first defect: the two narrow knots
now return the block's text.

``TestSharedExtractorIsTheOnlyPath`` pins the deduplication as behaviour rather
than as a name: it replaces ``LlmResponseText.extract`` and asserts every one of
the seven knots changes its answer. A knot that still owned a private copy would
be unaffected and fail here.
"""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, ClassVar
from unittest.mock import patch

from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.specializations.guardrails.fact_claim_extractor import FactClaimExtractor
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.specializations.rag.draft_verifier import DraftVerifier
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn_agents.specializations.rag.rag_synthesizer import RAGSynthesizer
from pirn_agents.specializations.structured_output.enum_classifier_attempt import (
    EnumClassifierAttempt,
)
from pirn_agents.specializations.structured_output.json_extractor_attempt import (
    JsonExtractorAttempt,
)
from pirn_agents.specializations.structured_output.yaml_extractor_attempt import (
    YamlExtractorAttempt,
)
from pirn_agents.types.messaging.agent_response import AgentResponse


class RawShapeLLMProvider(LLMProvider):
    """Returns one caller-supplied raw chat payload, whatever its shape."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Any:
        return self._raw

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[StreamDelta]:
        async def _aiter() -> AsyncIterator[StreamDelta]:
            yield StreamDelta(content="stub")

        return _aiter()

    async def close(self) -> None:
        return None


class TestBlockListContentIsExtracted(unittest.IsolatedAsyncioTestCase):
    """A block-list ``content`` yields the block's text, not ``str(mapping)``."""

    _block_response: ClassVar[Any] = {
        "role": "assistant",
        "content": [{"type": "text", "text": "Paris is the capital."}],
    }

    async def test_rag_synthesizer_reads_the_text_block(self) -> None:
        llm = RawShapeLLMProvider(self._block_response)
        knot = RAGSynthesizer(query="q", documents=[], llm=llm, _config=KnotConfig(id="synth"))
        response = await knot.process(query="q", documents=[], llm=llm)
        assert response.data == "Paris is the capital."

    async def test_draft_verifier_reads_the_text_block(self) -> None:
        llm = RawShapeLLMProvider(self._block_response)
        knot = DraftVerifier(
            query="q", draft="d", documents=[], llm=llm, _config=KnotConfig(id="verify")
        )
        response = await knot.process(query="q", draft="d", documents=[], llm=llm)
        assert response.data == "Paris is the capital."


class TestSharedExtractorIsTheOnlyPath(unittest.IsolatedAsyncioTestCase):
    """Replacing the shared extractor changes every knot's answer."""

    @staticmethod
    def _patch(text: str) -> Any:
        return patch.object(LlmResponseText, "extract", lambda self, raw: text)

    async def test_rag_synthesizer_routes_through_the_shared_extractor(self) -> None:
        llm = RawShapeLLMProvider("ignored")
        knot = RAGSynthesizer(query="q", documents=[], llm=llm, _config=KnotConfig(id="s"))
        with self._patch("routed"):
            response = await knot.process(query="q", documents=[], llm=llm)
        assert response.data == "routed"

    async def test_draft_verifier_routes_through_the_shared_extractor(self) -> None:
        llm = RawShapeLLMProvider("ignored")
        knot = DraftVerifier(
            query="q", draft="d", documents=[], llm=llm, _config=KnotConfig(id="v")
        )
        with self._patch("routed"):
            response = await knot.process(query="q", draft="d", documents=[], llm=llm)
        assert response.data == "routed"

    async def test_llm_chat_call_routes_through_the_shared_extractor(self) -> None:
        llm = RawShapeLLMProvider("ignored")
        knot = LLMChatCall(prompt="p", llm=llm, _config=KnotConfig(id="c"))
        with self._patch("routed"):
            assert await knot.process(prompt="p", llm=llm) == "routed"

    async def test_enum_classifier_attempt_routes_through_the_shared_extractor(self) -> None:
        llm = RawShapeLLMProvider("no")
        knot = EnumClassifierAttempt(
            prompt="p", llm=llm, labels=("yes", "no"), _config=KnotConfig(id="e")
        )
        with self._patch("yes"):
            assert await knot.process(prompt="p", llm=llm, labels=("yes", "no")) == "yes"

    async def test_json_extractor_attempt_routes_through_the_shared_extractor(self) -> None:
        llm = RawShapeLLMProvider("not json at all")
        knot = JsonExtractorAttempt(
            prompt="p", llm=llm, schema={"a": "int"}, prior_error="", _config=KnotConfig(id="j")
        )
        with self._patch('{"a": 1}'):
            parsed = await knot.process(prompt="p", llm=llm, schema={"a": "int"}, prior_error="")
        assert parsed == {"a": 1}

    async def test_yaml_extractor_attempt_routes_through_the_shared_extractor(self) -> None:
        llm = RawShapeLLMProvider("[not, a, mapping]")
        knot = YamlExtractorAttempt(
            prompt="p", llm=llm, schema={"a": "int"}, prior_error="", _config=KnotConfig(id="y")
        )
        with self._patch("a: 1"):
            parsed = await knot.process(prompt="p", llm=llm, schema={"a": "int"}, prior_error="")
        assert parsed == {"a": 1}

    async def test_fact_claim_extractor_routes_through_the_shared_extractor(self) -> None:
        llm = RawShapeLLMProvider("")
        response = AgentResponse(content="answer", finish_reason="stop")
        knot = FactClaimExtractor(response=response, llm=llm, _config=KnotConfig(id="f"))
        with self._patch("- the sky is blue\n- water is wet"):
            claims = await knot.process(response=response, llm=llm)
        assert claims == ["the sky is blue", "water is wet"]
