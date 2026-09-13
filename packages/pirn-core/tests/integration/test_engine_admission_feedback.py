"""Admission-gate runtime feedback through a real run (WS0).

An ``AdmissionObserver`` hears every admission and release with the queue
depth, wait, hold time and outcome, and can move the gate's caps mid-run
through ``event.gate.set_limit``.  That is the seam an adaptive concurrency
controller is written against.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.run_request import RunRequest
from pirn.engine.admission.admission_event import AdmissionEvent
from pirn.engine.admission.admission_limit_error import AdmissionLimitError
from pirn.engine.admission.admission_observer import AdmissionObserver
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.timeout(60)


class _Recorder(AdmissionObserver):
    def __init__(self) -> None:
        self.events: list[AdmissionEvent] = []

    def on_admit(self, event: AdmissionEvent) -> None:
        self.events.append(event)

    def on_release(self, event: AdmissionEvent) -> None:
        self.events.append(event)


class _Widen(AdmissionObserver):
    """Raises the ``api`` cap to *target* on the first release it sees."""

    def __init__(self, target: int) -> None:
        self.target = target
        self.widened = False

    def on_release(self, event: AdmissionEvent) -> None:
        if not self.widened and event.group == "api":
            event.gate.set_limit("api", self.target)
            self.widened = True


class _Gauge(PirnOpaqueValue):
    """Peak in-flight counter; opaque so it can travel as a config value."""

    def __init__(self) -> None:
        self.in_flight = 0
        self.peak = 0

    def enter(self) -> None:
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)

    def leave(self) -> None:
        self.in_flight -= 1


class _Call(Knot):
    async def process(self, x: int, gauge: _Gauge, seconds: float, **_: Any) -> int:
        gauge.enter()
        try:
            await asyncio.sleep(seconds)
        finally:
            gauge.leave()
        return x


class _Boom(Knot):
    async def process(self, x: int, **_: Any) -> int:
        raise RuntimeError("boom")


def _calls(gauge: _Gauge, width: int, seconds: float = 0.01) -> Tapestry:
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        for i in range(width):
            _Call(
                x=p,
                gauge=gauge,
                seconds=seconds,
                _config=KnotConfig(id=f"c{i}", concurrency_group="api"),
            )
    return t


async def test_every_admitted_knot_is_reported_twice_with_its_outcome() -> None:
    # Arrange
    recorder = _Recorder()
    with Tapestry(admission_observers=[recorder]) as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        bad = _Boom(x=p, _config=KnotConfig(id="bad", concurrency_group="api"))
        _Call(x=bad, gauge=_Gauge(), seconds=0.0, _config=KnotConfig(id="skipped"))
        _Call(
            x=p, gauge=_Gauge(), seconds=0.0, _config=KnotConfig(id="ok", concurrency_group="api")
        )

    # Act
    result = await t.run(RunRequest(concurrency=ConcurrencyLimits(groups={"api": 1})))

    # Assert
    admits = {e.knot_id for e in recorder.events if e.kind == "admit"}
    releases = {e.knot_id: e.outcome for e in recorder.events if e.kind == "release"}
    assert admits == {"p", "bad", "skipped", "ok"}
    assert releases == {"p": "ok", "bad": "err", "skipped": "skipped", "ok": "ok"}
    assert all(e.run_id == result.run_id for e in recorder.events)
    api_release = next(e for e in recorder.events if e.kind == "release" and e.knot_id == "ok")
    assert api_release.group == "api"
    assert api_release.group_limit == 1
    assert api_release.held_seconds is not None and api_release.held_seconds >= 0.0


async def test_queue_depth_and_wait_are_reported_under_a_tight_cap() -> None:
    # Arrange: four api calls, one at a time -- the first admit sees three waiting.
    recorder = _Recorder()
    t = _calls(_Gauge(), 4)

    # Act
    await t.run(
        RunRequest(concurrency=ConcurrencyLimits(groups={"api": 1})),
        admission_observers=[recorder],
    )

    # Assert
    api_admits = [e for e in recorder.events if e.kind == "admit" and e.group == "api"]
    assert [e.waiting for e in api_admits] == [3, 2, 1, 0]
    assert api_admits[0].queued_seconds >= 0.0
    assert api_admits[-1].queued_seconds > 0.0
    assert all(e.group_in_flight == 1 for e in api_admits)


async def test_an_observer_can_widen_a_cap_mid_run() -> None:
    # Arrange: eight calls under a cap of one; the observer raises it to four
    # after the first release, so later calls overlap.
    gauge = _Gauge()
    widen = _Widen(target=4)
    t = _calls(gauge, 8, seconds=0.05)

    # Act
    result = await t.run(
        RunRequest(concurrency=ConcurrencyLimits(groups={"api": 1})),
        admission_observers=[widen],
    )

    # Assert
    assert result.succeeded
    assert widen.widened
    assert gauge.peak == 4


async def test_without_a_widening_observer_the_cap_holds() -> None:
    gauge = _Gauge()
    t = _calls(gauge, 8, seconds=0.02)
    await t.run(RunRequest(concurrency=ConcurrencyLimits(groups={"api": 1})))
    assert gauge.peak == 1


async def test_run_observers_replace_tapestry_observers() -> None:
    # Arrange
    default = _Recorder()
    per_run = _Recorder()
    t = Tapestry(admission_observers=[default])
    with t:
        Parameter("x", int, default=1, _config=KnotConfig(id="p"))

    # Act
    await t.run(RunRequest(), admission_observers=[per_run])
    await t.run(RunRequest(), admission_observers=[])
    await t.run(RunRequest())

    # Assert
    assert [e.kind for e in per_run.events] == ["admit", "release"]
    assert [e.kind for e in default.events] == ["admit", "release"]
    assert t.admission_observers == [default]


async def test_an_unbounded_run_refuses_to_move_a_cap() -> None:
    # Arrange
    seen: list[str] = []

    class _Tweaker(AdmissionObserver):
        def on_release(self, event: AdmissionEvent) -> None:
            try:
                event.gate.set_limit("api", 2)
            except AdmissionLimitError as exc:
                seen.append(type(exc).__name__)

    with Tapestry(admission_observers=[_Tweaker()]) as t:
        Parameter("x", int, default=1, _config=KnotConfig(id="p"))

    # Act
    result = await t.run(RunRequest())

    # Assert
    assert result.succeeded
    assert seen == ["AdmissionLimitError"]


async def test_a_raising_observer_does_not_fail_the_run() -> None:
    class _Faulty(AdmissionObserver):
        def on_admit(self, event: AdmissionEvent) -> None:
            raise RuntimeError("observer bug")

    with Tapestry(admission_observers=[_Faulty()]) as t:
        Parameter("x", int, default=1, _config=KnotConfig(id="p"))
    result = await t.run(RunRequest())
    assert result.succeeded


async def test_synthetic_failures_report_err_and_release() -> None:
    recorder = _Recorder()
    with Tapestry(admission_observers=[recorder]) as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        bad = _Boom(x=p, _config=KnotConfig(id="bad"))
        _Call(
            x=bad,
            gauge=_Gauge(),
            seconds=0.0,
            _config=KnotConfig(id="strict", error_policy=ErrorPolicy.REQUIRE_ALL_PARENTS),
        )
    await t.run(RunRequest())
    strict = [e for e in recorder.events if e.knot_id == "strict"]
    assert [e.kind for e in strict] == ["admit", "release"]
    assert strict[1].outcome == "err"
