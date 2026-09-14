"""``AdmissionFeedback`` — the engine's reporter of admissions to observers.

One per run.  The engine tells it when knots become ready, are admitted and
are released; it keeps the little state an observer cannot get from the gate
alone — when each knot became ready, when it was admitted, how many tickets
are held run-wide and per group — and builds one ``AdmissionEvent`` per
admission and release for every ``AdmissionObserver`` of the run.

It lives beside the gate rather than inside it on purpose.  A gate counts
capacity and nothing else; the queue depth, the wait time and the outcome
are the engine's to know, and an observer wants all of them in one event.
With no observers every method returns at once, so a run that nobody watches
pays nothing.

Algorithm:
    1. ``enqueued(ids)`` stamps each knot's ready time.
    2. ``admitted(knot_id, ticket, waiting)`` stamps the admit time, bumps
       the run-wide and group counters, and reports an ``"admit"`` event
       whose ``queued_seconds`` is admit time minus ready time.
    3. ``released(ticket, outcome, waiting)`` decrements the counters and
       reports a ``"release"`` event whose ``held_seconds`` is now minus
       the admit time and whose ``outcome`` is how the knot ended.
    4. A hook that raises is logged at WARNING; the run continues.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from pirn.engine.admission.admission_event import AdmissionEvent

if TYPE_CHECKING:
    from pirn.engine.admission.admission import Admission
    from pirn.engine.admission.admission_observer import AdmissionObserver
    from pirn.engine.admission.admission_ticket import AdmissionTicket

_log = logging.getLogger(__name__)


class AdmissionFeedback:
    """Reports a run's admissions and releases to its ``AdmissionObserver``s."""

    def __init__(
        self,
        run_id: str,
        gate: Admission,
        observers: Iterable[AdmissionObserver] = (),
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Bind the reporter to one run.

        Args:
            run_id: The run whose admissions are reported.
            gate: The run's gate; every event carries it.
            observers: The observers to report to.  Empty means silent.
            clock: Monotonic clock in seconds; defaults to
                :func:`time.monotonic`.  Injected by tests.
        """
        self._run_id = run_id
        self._gate = gate
        self._observers = list(observers)
        self._clock = clock if clock is not None else time.monotonic
        self._ready_since: dict[str, float] = {}
        self._admitted_at: dict[str, float] = {}
        self._in_flight = 0
        self._group_in_flight: Counter[str] = Counter()

    @property
    def active(self) -> bool:
        """Whether anyone is listening."""
        return bool(self._observers)

    @property
    def in_flight(self) -> int:
        """Tickets currently held, as this reporter counts them."""
        return self._in_flight

    def enqueued(self, knot_ids: Iterable[str]) -> None:
        """Note that *knot_ids* just became ready."""
        if not self._observers:
            return
        now = self._clock()
        for knot_id in knot_ids:
            self._ready_since[knot_id] = now

    def admitted(self, knot_id: str, ticket: AdmissionTicket, waiting: int) -> None:
        """Report that *knot_id* took the slot *ticket* records.

        Args:
            knot_id: The admitted knot.
            ticket: Its ticket.
            waiting: Knots of its group still waiting after this admission.
        """
        if not self._observers:
            return
        now = self._clock()
        self._admitted_at[knot_id] = now
        self._in_flight += 1
        if ticket.group is not None:
            self._group_in_flight[ticket.group] += 1
        queued = now - self._ready_since.pop(knot_id, now)
        event = self._event("admit", knot_id, ticket, waiting, queued, None, None)
        for observer in self._observers:
            self._notify(observer, "on_admit", event)

    def released(self, ticket: AdmissionTicket, outcome: str, waiting: int) -> None:
        """Report that *ticket*'s knot gave its slot back.

        Args:
            ticket: The released ticket.
            outcome: ``"ok"``, ``"err"``, ``"skipped"`` or ``"aborted"``.
            waiting: Knots of its group still waiting after this release.
        """
        if not self._observers:
            return
        now = self._clock()
        held = now - self._admitted_at.pop(ticket.knot_id, now)
        self._in_flight = max(0, self._in_flight - 1)
        if ticket.group is not None:
            self._group_in_flight[ticket.group] = max(0, self._group_in_flight[ticket.group] - 1)
        event = self._event("release", ticket.knot_id, ticket, waiting, 0.0, held, outcome)
        for observer in self._observers:
            self._notify(observer, "on_release", event)

    def _event(
        self,
        kind: str,
        knot_id: str,
        ticket: AdmissionTicket,
        waiting: int,
        queued: float,
        held: float | None,
        outcome: str | None,
    ) -> AdmissionEvent:
        group = ticket.group
        return AdmissionEvent(
            kind=kind,
            run_id=self._run_id,
            knot_id=knot_id,
            group=group,
            in_flight=self._in_flight,
            group_in_flight=self._group_in_flight[group] if group is not None else 0,
            max_in_flight=self._gate.current_limit(None),
            group_limit=self._gate.current_limit(group) if group is not None else None,
            waiting=waiting,
            queued_seconds=queued,
            held_seconds=held,
            outcome=outcome,
            gate=self._gate,
        )

    @staticmethod
    def _notify(observer: AdmissionObserver, hook: str, event: AdmissionEvent) -> None:
        try:
            if hook == "on_admit":
                observer.on_admit(event)
            else:
                observer.on_release(event)
        except Exception:
            _log.warning(
                "AdmissionObserver %r raised in %s for knot %r; ignored",
                type(observer).__name__,
                hook,
                event.knot_id,
                exc_info=True,
            )
