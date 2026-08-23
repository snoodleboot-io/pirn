"""Unit tests for :class:`SpecialistInvocation`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.specialist_invocation import (
    SpecialistInvocation,
)
from pirn_agents.specializations.multi_agent.specialist_invocation_error import (
    SpecialistInvocationError,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import response_sink


class _EchoSpecialist(SubTapestry):
    """Returns an :class:`AgentResponse` echoing the task it received."""

    def __init__(self, *, task: Any = "", _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str = "", **_: Any) -> Knot:
        return response_sink(
            AgentResponse(content=f"echo:{task}", finish_reason="stop"),
            f"{self.config.id}_reply",
        )


class _RawStringSpecialist(SubTapestry):
    """Returns a bare ``str`` — not an :class:`AgentResponse`."""

    def __init__(self, *, task: Any = "", _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str = "", **_: Any) -> Knot:
        class _StrSink(Source):
            async def process(self, **_: Any) -> str:
                return f"plain:{task}"

        return _StrSink(_config=KnotConfig(id=f"{self.config.id}_raw"))


class _FailingSpecialist(SubTapestry):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Knot:
        raise RuntimeError("boom")


def _make_invocation(specialist: SubTapestry) -> SpecialistInvocation:
    with Tapestry():
        return SpecialistInvocation(
            specialist=specialist,
            task="t",
            _config=KnotConfig(id="inv"),
        )


def _make_specialist(cls: type[SubTapestry], id_: str) -> SubTapestry:
    with Tapestry():
        return cls(_config=KnotConfig(id=id_))


class TestSpecialistInvocationProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_specialist_agent_response(self) -> None:
        spec = _make_specialist(_EchoSpecialist, "echo")
        inv = _make_invocation(spec)
        out = await inv.process(task="ask")
        assert isinstance(out, AgentResponse)
        assert out.content == "echo:ask"

    async def test_normalises_non_agent_response(self) -> None:
        spec = _make_specialist(_RawStringSpecialist, "raw")
        inv = _make_invocation(spec)
        out = await inv.process(task="ask")
        assert isinstance(out, AgentResponse)
        assert out.content == "plain:ask"
        assert out.finish_reason == "stop"

    async def test_holds_specialist_off_the_parent_set(self) -> None:
        # The specialist must NOT be a graph parent — it is opaque data this
        # knot invokes itself, held on a _mutable_ slot.
        spec = _make_specialist(_EchoSpecialist, "echo")
        inv = _make_invocation(spec)
        assert spec not in inv.parents.values()
        assert getattr(inv, "_mutable_specialist") is spec  # noqa: B009

    async def test_propagates_specialist_failure(self) -> None:
        spec = _make_specialist(_FailingSpecialist, "bad")
        inv = _make_invocation(spec)
        with self.assertRaises(SpecialistInvocationError):
            await inv.process(task="ask")

    async def test_tapestry_run_integration(self) -> None:
        spec = _make_specialist(_EchoSpecialist, "echo")
        with Tapestry() as t:
            SpecialistInvocation(
                specialist=spec,
                task="hello",
                _config=KnotConfig(id="inv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["inv"]
        assert isinstance(out, AgentResponse)
        assert out.content == "echo:hello"
