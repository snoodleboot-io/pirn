"""Unit tests for :class:`ConstitutionalFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.reflection.constitutional_filter import (
    ConstitutionalFilter,
)
from pirn.domains.agents.specializations.reflection.constitutional_violation_error import (
    ConstitutionalViolationError,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


@knot
async def good_response() -> AgentResponse:
    return AgentResponse(content="A helpful and safe reply.")


@knot
async def bad_response() -> AgentResponse:
    return AgentResponse(content="A harmful reply.")


class TestConstitutionalFilterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_compliant_response_passes_through_unchanged(self) -> None:
        llm = StubLLMProvider(["COMPLIANT"])
        with Tapestry() as t:
            r = good_response(_config=KnotConfig(id="r"))
            ConstitutionalFilter(
                response=r,
                principles=("Be helpful.", "Be harmless."),
                llm=llm,
                _config=KnotConfig(id="cf"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["cf"]
        assert isinstance(response, AgentResponse)
        assert response.content == "A helpful and safe reply."

    async def test_violation_triggers_revision(self) -> None:
        llm = StubLLMProvider(["Revised: safe reply.", "COMPLIANT"])
        with Tapestry() as t:
            r = bad_response(_config=KnotConfig(id="r"))
            ConstitutionalFilter(
                response=r,
                principles=("Be harmless.",),
                llm=llm,
                max_revisions=3,
                _config=KnotConfig(id="cf"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["cf"]
        assert response.content == "Revised: safe reply."

    async def test_raises_after_max_revisions(self) -> None:
        llm = StubLLMProvider(["still bad"] * 5)
        with Tapestry() as t:
            r = bad_response(_config=KnotConfig(id="r"))
            ConstitutionalFilter(
                response=r,
                principles=("Be safe.",),
                llm=llm,
                max_revisions=2,
                _config=KnotConfig(id="cf"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_zero_max_revisions(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry() as t:
            r = good_response(_config=KnotConfig(id="r"))
            ConstitutionalFilter(
                response=r,
                principles=("safe",),
                llm=llm,
                max_revisions=0,
                _config=KnotConfig(id="cf"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                r = good_response(_config=KnotConfig(id="r"))
                ConstitutionalFilter(
                    response=r,
                    principles=("safe",),
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="cf"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_llm_provider(self) -> None:
        response = AgentResponse(content="hello")
        with Tapestry():
            k = ConstitutionalFilter.__new__(ConstitutionalFilter)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(
                response=response,
                principles=("be safe",),
                llm="not-an-llm",  # type: ignore[arg-type]
            )

    async def test_process_rejects_zero_max_revisions(self) -> None:
        response = AgentResponse(content="hello")
        llm = StubLLMProvider(["x"])
        with Tapestry():
            k = ConstitutionalFilter.__new__(ConstitutionalFilter)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(ValueError):
            await k.process(
                response=response,
                principles=("be safe",),
                llm=llm,
                max_revisions=0,
            )
