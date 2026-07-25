"""Tests for :class:`DraftVerifier`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.draft_verifier import DraftVerifier
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


def _verifier() -> DraftVerifier:
    with Tapestry():
        knot = DraftVerifier.__new__(DraftVerifier)
        object.__setattr__(knot, "_config", KnotConfig(id="verify"))
    return knot


class TestDraftVerifier(unittest.IsolatedAsyncioTestCase):
    async def test_verifies_draft_against_documents(self) -> None:
        llm = StubLLMProvider(["verified [1]"])
        knot = _verifier()
        response = await knot.process(
            query="q",
            draft="draft claim",
            documents=[{"text": "supporting evidence"}],
            llm=llm,
        )
        assert isinstance(response, AgentResponse)
        assert response.content == "verified [1]"
        prompt = llm.calls[0][-1]["content"]
        assert "draft claim" in prompt
        assert "supporting evidence" in prompt

    async def test_handles_no_documents(self) -> None:
        llm = StubLLMProvider(["unverified"])
        knot = _verifier()
        response = await knot.process(query="q", draft="d", documents=[], llm=llm)
        assert response.content == "unverified"
        assert "(no documents retrieved)" in llm.calls[0][-1]["content"]

    async def test_rejects_non_string_draft(self) -> None:
        knot = _verifier()
        with self.assertRaisesRegex(TypeError, "draft must be a string"):
            await knot.process(query="q", draft=1, documents=[], llm=StubLLMProvider(["x"]))  # type: ignore[arg-type]
