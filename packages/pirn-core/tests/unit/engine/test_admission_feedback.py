"""Unit tests for ``AdmissionFeedback`` and the observer/event contract (WS0).

A fake clock makes the queued and held durations exact, and a recording
observer captures every event so its fields can be asserted one by one.
"""

from __future__ import annotations

import logging
import unittest

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.engine.admission.admission_event import AdmissionEvent
from pirn.engine.admission.admission_observer import AdmissionObserver
from pirn.engine.admission.admission_ticket import AdmissionTicket
from pirn.engine.admission.limited_admission_gate import LimitedAdmissionGate
from pirn.engine.admission.unbounded_admission_gate import UnboundedAdmissionGate
from pirn.engine.admission_feedback import AdmissionFeedback


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class _Recorder(AdmissionObserver):
    def __init__(self) -> None:
        self.events: list[AdmissionEvent] = []

    def on_admit(self, event: AdmissionEvent) -> None:
        self.events.append(event)

    def on_release(self, event: AdmissionEvent) -> None:
        self.events.append(event)


class _Faulty(AdmissionObserver):
    def on_admit(self, event: AdmissionEvent) -> None:
        raise RuntimeError("observer bug")

    def on_release(self, event: AdmissionEvent) -> None:
        raise RuntimeError("observer bug")


def _admit_event(gate: UnboundedAdmissionGate) -> AdmissionEvent:
    return AdmissionEvent(
        kind="admit",
        run_id="r",
        knot_id="k",
        group=None,
        in_flight=1,
        group_in_flight=0,
        max_in_flight=None,
        group_limit=None,
        waiting=0,
        queued_seconds=0.0,
        held_seconds=None,
        outcome=None,
        gate=gate,
    )


class TestObserverInterface(unittest.TestCase):
    def test_hooks_are_no_ops_by_default(self) -> None:
        event = _admit_event(UnboundedAdmissionGate())
        observer = AdmissionObserver()
        self.assertIsNone(observer.on_admit(event))
        self.assertIsNone(observer.on_release(event))

    def test_event_is_frozen_and_compares_without_the_gate(self) -> None:
        a = _admit_event(UnboundedAdmissionGate())
        b = _admit_event(UnboundedAdmissionGate())
        self.assertEqual(a, b)
        self.assertNotIn("gate", repr(a))
        with self.assertRaises(AttributeError):
            a.kind = "release"  # type: ignore[misc]


class TestAdmissionFeedback(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = _Clock()
        self.gate = LimitedAdmissionGate(ConcurrencyLimits(max_in_flight=4, groups={"api": 2}))
        self.recorder = _Recorder()
        self.feedback = AdmissionFeedback("run-1", self.gate, [self.recorder], clock=self.clock)

    def test_silent_and_inactive_without_observers(self) -> None:
        feedback = AdmissionFeedback("run-1", self.gate, [], clock=self.clock)
        self.assertFalse(feedback.active)
        feedback.enqueued(["a"])
        feedback.admitted("a", AdmissionTicket(knot_id="a"), 0)
        feedback.released(AdmissionTicket(knot_id="a"), "ok", 0)
        self.assertEqual(feedback.in_flight, 0)

    def test_admit_event_reports_queue_wait_and_counters(self) -> None:
        # Arrange
        self.feedback.enqueued(["a"])
        self.clock.now += 1.5

        # Act
        self.feedback.admitted("a", AdmissionTicket(knot_id="a", group="api"), waiting=3)

        # Assert
        (event,) = self.recorder.events
        self.assertEqual(event.kind, "admit")
        self.assertEqual(event.run_id, "run-1")
        self.assertEqual(event.knot_id, "a")
        self.assertEqual(event.group, "api")
        self.assertEqual(event.in_flight, 1)
        self.assertEqual(event.group_in_flight, 1)
        self.assertEqual(event.max_in_flight, 4)
        self.assertEqual(event.group_limit, 2)
        self.assertEqual(event.waiting, 3)
        self.assertEqual(event.queued_seconds, 1.5)
        self.assertIsNone(event.held_seconds)
        self.assertIsNone(event.outcome)
        self.assertIs(event.gate, self.gate)

    def test_release_event_reports_hold_time_and_outcome(self) -> None:
        # Arrange
        ticket = AdmissionTicket(knot_id="a", group="api")
        self.feedback.enqueued(["a"])
        self.feedback.admitted("a", ticket, waiting=0)
        self.clock.now += 2.25

        # Act
        self.feedback.released(ticket, "err", waiting=1)

        # Assert
        event = self.recorder.events[-1]
        self.assertEqual(event.kind, "release")
        self.assertEqual(event.outcome, "err")
        self.assertEqual(event.held_seconds, 2.25)
        self.assertEqual(event.in_flight, 0)
        self.assertEqual(event.group_in_flight, 0)
        self.assertEqual(event.waiting, 1)

    def test_ungrouped_knot_reports_no_group_limit(self) -> None:
        self.feedback.admitted("a", AdmissionTicket(knot_id="a"), waiting=0)
        (event,) = self.recorder.events
        self.assertIsNone(event.group)
        self.assertIsNone(event.group_limit)
        self.assertEqual(event.group_in_flight, 0)

    def test_an_unqueued_admission_has_zero_wait(self) -> None:
        self.feedback.admitted("a", AdmissionTicket(knot_id="a"), waiting=0)
        self.assertEqual(self.recorder.events[0].queued_seconds, 0.0)

    def test_the_live_limit_is_read_at_event_time(self) -> None:
        self.gate.set_limit("api", 7)
        self.feedback.admitted("a", AdmissionTicket(knot_id="a", group="api"), waiting=0)
        self.assertEqual(self.recorder.events[0].group_limit, 7)

    def test_a_raising_observer_is_logged_and_the_others_still_hear(self) -> None:
        # Arrange
        feedback = AdmissionFeedback(
            "run-1", self.gate, [_Faulty(), self.recorder], clock=self.clock
        )

        # Act
        with self.assertLogs("pirn.engine.admission_feedback", level=logging.WARNING) as logs:
            feedback.admitted("a", AdmissionTicket(knot_id="a"), waiting=0)
            feedback.released(AdmissionTicket(knot_id="a"), "ok", waiting=0)

        # Assert
        self.assertEqual([e.kind for e in self.recorder.events], ["admit", "release"])
        self.assertEqual(len(logs.records), 2)
        self.assertIn("_Faulty", logs.records[0].getMessage())
