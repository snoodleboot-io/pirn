"""Tests for the AIMD concurrency controller (ADR agents-speaks-core, WS4b).

``AdaptiveConcurrencyController`` is now an
:class:`~pirn.engine.admission.admission_observer.AdmissionObserver`: the
engine calls ``on_admit``/``on_release`` with an ``AdmissionEvent``, and the
controller reacts by calling ``AdmissionGate.set_limit`` on the fake gate the
event carries. ``on_throttle`` is unchanged — still called directly by a
rate-limited item, since ``AdmissionEvent`` carries no exception detail (see
the module docstring).
"""

from __future__ import annotations

import pytest
from pirn.engine.admission.admission_event import AdmissionEvent

from pirn_agents.batch.adaptive_concurrency_controller import AdaptiveConcurrencyController


class _FakeGate:
    """Records every ``set_limit`` call; nothing else is needed for these tests."""

    def __init__(self) -> None:
        self.limits: list[tuple[str | None, int]] = []

    def set_limit(self, group: str | None, limit: int) -> None:
        self.limits.append((group, limit))


def _release(
    controller: AdaptiveConcurrencyController,
    *,
    outcome: str,
    group: str | None = "g",
    gate: _FakeGate | None = None,
) -> _FakeGate:
    gate = gate if gate is not None else _FakeGate()
    controller.on_release(
        AdmissionEvent(
            kind="release",
            run_id="run-1",
            knot_id="item-1",
            group=group,
            in_flight=0,
            group_in_flight=0,
            max_in_flight=None,
            group_limit=None,
            waiting=0,
            queued_seconds=0.0,
            held_seconds=0.01,
            outcome=outcome,
            gate=gate,  # type: ignore[arg-type]
        )
    )
    return gate


def _admit(
    controller: AdaptiveConcurrencyController,
    *,
    group: str | None = "g",
    gate: _FakeGate | None = None,
) -> _FakeGate:
    gate = gate if gate is not None else _FakeGate()
    controller.on_admit(
        AdmissionEvent(
            kind="admit",
            run_id="run-1",
            knot_id="item-1",
            group=group,
            in_flight=1,
            group_in_flight=1,
            max_in_flight=None,
            group_limit=None,
            waiting=0,
            queued_seconds=0.0,
            held_seconds=None,
            outcome=None,
            gate=gate,  # type: ignore[arg-type]
        )
    )
    return gate


class TestAimdBehaviour:
    def test_starts_at_max_by_default(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=8)
        assert controller.limit() == 8

    def test_throttle_halves_limit(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=8, decrease_factor=0.5)
        controller.on_throttle()
        assert controller.limit() == 4
        controller.on_throttle()
        assert controller.limit() == 2

    def test_successful_release_additively_increases(self) -> None:
        controller = AdaptiveConcurrencyController(
            min_limit=1, max_limit=8, initial=2, increase=1.0, group="g"
        )
        _release(controller, outcome="ok")
        assert controller.limit() == 3

    def test_never_drops_below_min(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=2, max_limit=8, decrease_factor=0.1)
        for _ in range(10):
            controller.on_throttle()
        assert controller.limit() == 2

    def test_never_climbs_above_max(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=4, initial=4, group="g")
        for _ in range(10):
            _release(controller, outcome="ok")
        assert controller.limit() == 4

    def test_converges_back_up_after_throttle(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=8, initial=8, group="g")
        controller.on_throttle()  # 8 -> 4
        assert controller.limit() == 4
        _release(controller, outcome="ok")  # 4 -> 5
        _release(controller, outcome="ok")  # 5 -> 6
        assert controller.limit() == 6

    def test_a_failed_release_does_not_decrease(self) -> None:
        """Only on_throttle decreases; a plain 'err' outcome does not.

        AdmissionEvent carries no exception detail, so treating every err as
        a throttle would also fire on an ordinary bug in the per-item
        callable -- the pre-migration controller never did that either (only
        RateLimitSignal triggered a decrease).
        """
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=8, initial=4, group="g")
        _release(controller, outcome="err")
        assert controller.limit() == 4

    def test_release_of_a_different_group_is_ignored(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=8, initial=4, group="g")
        _release(controller, outcome="ok", group="other")
        assert controller.limit() == 4

    def test_release_calls_set_limit_on_the_events_gate(self) -> None:
        controller = AdaptiveConcurrencyController(
            min_limit=1, max_limit=8, initial=2, increase=1.0, group="g"
        )
        gate = _release(controller, outcome="ok")
        assert gate.limits == [("g", 3)]

    def test_throttle_steers_the_gate_seen_on_a_prior_admit(self) -> None:
        controller = AdaptiveConcurrencyController(
            min_limit=1, max_limit=8, initial=8, decrease_factor=0.5, group="g"
        )
        gate = _admit(controller)
        controller.on_throttle()
        assert gate.limits == [("g", 4)]

    def test_bind_to_group_changes_which_events_it_reacts_to(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=8, initial=2)
        controller.bind_to_group("items")
        gate = _release(controller, outcome="ok", group="items")
        assert controller.limit() == 3
        assert gate.limits == [("items", 3)]


class TestValidation:
    def test_rejects_min_below_one(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveConcurrencyController(min_limit=0, max_limit=4)

    def test_rejects_max_below_min(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveConcurrencyController(min_limit=4, max_limit=2)

    def test_rejects_decrease_factor_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveConcurrencyController(min_limit=1, max_limit=4, decrease_factor=1.5)

    def test_rejects_non_positive_increase(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveConcurrencyController(min_limit=1, max_limit=4, increase=0)

    def test_rejects_initial_out_of_bounds(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveConcurrencyController(min_limit=1, max_limit=4, initial=9)
