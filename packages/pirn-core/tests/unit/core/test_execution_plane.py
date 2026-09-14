"""``ExecutionPlane`` — the value object ``Tapestry.run`` publishes for inner runs."""

from __future__ import annotations

import dataclasses
import unittest
from typing import Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.execution_plane import ExecutionPlane
from pirn.core.identity.identity_resolver import IdentityResolver
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.engine.admission.limited_admission import LimitedAdmission
from pirn.engine.admission.unbounded_admission import UnboundedAdmission
from pirn.engine.dispatchers.local_dispatcher import LocalDispatcher
from pirn.tapestry import Tapestry


class _Nobody(IdentityResolver):
    def resolve(self) -> str | None:
        return None


class _Probe(Knot):
    def __init__(self, *, seen: list[ExecutionPlane | None], **kwargs: Any) -> None:
        self._seen = seen
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> int:
        self._seen.append(ExecutionPlane.current())
        return 1


class TestExecutionPlaneValue(unittest.TestCase):
    def test_is_frozen(self) -> None:
        plane = ExecutionPlane(
            dispatcher=LocalDispatcher(),
            gate=UnboundedAdmission(),
            limits=None,
            admission_observers=(),
            replay=None,
            identity_resolver=_Nobody(),
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plane.limits = ConcurrencyLimits()  # type: ignore[misc]

    def test_current_is_none_outside_a_run(self) -> None:
        self.assertIsNone(ExecutionPlane.current())


class TestExecutionPlaneIsPublishedForTheRun(unittest.IsolatedAsyncioTestCase):
    async def test_a_knot_reads_the_plane_its_run_executes_under(self) -> None:
        seen: list[ExecutionPlane | None] = []
        dispatcher = LocalDispatcher()
        with Tapestry(dispatcher=dispatcher, concurrency=ConcurrencyLimits(max_in_flight=2)) as t:
            _Probe(seen=seen, _config=KnotConfig(id="probe"))

        await t.run(RunRequest())

        (plane,) = seen
        assert plane is not None
        self.assertIs(plane.dispatcher, dispatcher)
        self.assertIsInstance(plane.gate, LimitedAdmission)
        self.assertEqual(plane.limits, ConcurrencyLimits(max_in_flight=2))
        self.assertIsNone(plane.replay)
        self.assertIs(plane.identity_resolver, t.identity_resolver)

    async def test_the_plane_is_cleared_once_the_run_ends(self) -> None:
        with Tapestry() as t:
            _Probe(seen=[], _config=KnotConfig(id="probe"))
        await t.run(RunRequest())
        self.assertIsNone(ExecutionPlane.current())

    async def test_a_root_run_without_limits_gets_the_unbounded_gate(self) -> None:
        seen: list[ExecutionPlane | None] = []
        with Tapestry() as t:
            _Probe(seen=seen, _config=KnotConfig(id="probe"))
        await t.run(RunRequest())
        (plane,) = seen
        assert plane is not None
        self.assertIsInstance(plane.gate, UnboundedAdmission)
        self.assertIsNone(plane.limits)
