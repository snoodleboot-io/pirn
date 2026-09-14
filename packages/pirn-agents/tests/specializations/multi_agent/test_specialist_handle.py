"""Tests for :meth:`SpecialistHandle.run`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.specialist_handle import SpecialistHandle
from pirn_agents.specializations.multi_agent.specialist_invocation_error import (
    SpecialistInvocationError,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import response_sink


class _EchoSpecialist(SubTapestry):
    """Contract-honouring double: returns the sink knot, not the answer."""

    def __init__(self, *, task: Any = "", _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str = "", **_: Any) -> Knot:
        return response_sink(
            AgentResponse(content=f"echo:{task}", finish_reason="stop"),
            "echo_reply",
        )


class _ExplodingSpecialist(SubTapestry):
    def __init__(self, *, task: Any = "", _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str = "", **_: Any) -> Knot:
        raise ValueError("specialist blew up")


class TestInvokeSpecialist(unittest.IsolatedAsyncioTestCase):
    async def test_returns_the_sink_output_not_the_sink_knot(self) -> None:
        """The whole point: ``process()`` returns a Knot, ``__call__`` runs it."""
        with Tapestry():
            spec = _EchoSpecialist(_config=KnotConfig(id="echo"))
        result = await SpecialistHandle(spec).run(task="hello")
        assert isinstance(result, AgentResponse)
        assert result.content == "echo:hello"

    async def test_inputs_override_construction_values(self) -> None:
        with Tapestry():
            spec = _EchoSpecialist(task="at-construction", _config=KnotConfig(id="echo2"))
        result = await SpecialistHandle(spec).run(task="at-call")
        assert isinstance(result, AgentResponse)
        assert result.content == "echo:at-call"

    async def test_a_failing_specialist_raises_instead_of_returning_a_value(self) -> None:
        """``__call__`` captures the failure as ``Err``; silently returning it would
        let the caller coerce a non-answer into an ``AgentResponse``."""
        with Tapestry():
            spec = _ExplodingSpecialist(_config=KnotConfig(id="boom"))
        with self.assertRaises(SpecialistInvocationError) as ctx:
            await SpecialistHandle(spec).run(task="anything")
        assert ctx.exception.specialist_id == "boom"
        assert "specialist blew up" in ctx.exception.reason


class TestSpecialistInvocationError(unittest.TestCase):
    def test_message_names_the_specialist_and_the_reason(self) -> None:
        err = SpecialistInvocationError("spec_a", "ValueError: nope")
        assert err.specialist_id == "spec_a"
        assert err.reason == "ValueError: nope"
        assert str(err) == "specialist 'spec_a' produced no output: ValueError: nope"

    def test_a_non_sub_tapestry_is_refused(self) -> None:
        with self.assertRaises(TypeError):
            SpecialistHandle(object())  # type: ignore[arg-type]


class TestSpecialistRegistryByName(unittest.TestCase):
    """``SpecialistHandle.by_name`` — the typed ``{name: specialist}`` registry."""

    def test_returns_the_registry_in_order(self) -> None:
        with Tapestry():
            first = _EchoSpecialist(_config=KnotConfig(id="first"))
            second = _EchoSpecialist(_config=KnotConfig(id="second"))
        registry = SpecialistHandle.by_name({"b": first, "a": second}, owner="Owner")
        assert list(registry) == ["b", "a"]
        assert registry["b"] is first

    def test_rejects_a_non_mapping_or_empty_registry(self) -> None:
        for bad in (None, [], {}):
            with self.assertRaisesRegex(
                ValueError, "Owner: specialists must be a non-empty mapping"
            ):
                SpecialistHandle.by_name(bad, owner="Owner")

    def test_rejects_a_non_string_name(self) -> None:
        with Tapestry():
            spec = _EchoSpecialist(_config=KnotConfig(id="named"))
        with self.assertRaisesRegex(TypeError, "Owner: specialist names must be strings"):
            SpecialistHandle.by_name({1: spec}, owner="Owner")

    def test_rejects_a_non_sub_tapestry_specialist(self) -> None:
        with self.assertRaisesRegex(TypeError, "Owner: specialist 'x' must be a SubTapestry"):
            SpecialistHandle.by_name({"x": object()}, owner="Owner")
