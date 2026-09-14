"""``AdmissionEvent`` — one admission or release, as reported to observers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.engine.admission.admission import Admission


@dataclass(frozen=True, slots=True)
class AdmissionEvent:
    """What an ``AdmissionObserver`` learns each time a knot takes or frees a slot.

    Reported by the engine (``AdmissionFeedback``), which is the one place
    that sees every side of an admission at once: the gate's counters, the
    ready queue's depth, the moment the knot became ready, and — on release
    — how the knot ended.  An adaptive controller has everything it needs
    here to steer ``gate.set_limit`` (ADR agents-speaks-core, WS0).

    Attributes:
        kind: ``"admit"`` when the knot took its slot, ``"release"`` when it
            gave it back.
        run_id: The run the knot belongs to.
        knot_id: The knot.
        group: Its ``KnotConfig.concurrency_group``, or ``None``.
        in_flight: Tickets held run-wide after this event.
        group_in_flight: Tickets held by the knot's group after this event
            (``0`` for an ungrouped knot).
        max_in_flight: The gate's run-wide cap right now, or ``None``.
        group_limit: The group's cap right now, or ``None`` when the knot
            has no group or the group is uncapped.
        waiting: Knots of the same group (ungrouped knots for ``None``)
            still waiting in the ready queue after this event.
        queued_seconds: How long the knot waited between becoming ready and
            being admitted.
        held_seconds: How long the knot held its slot; ``None`` on admit.
        outcome: ``"ok"``, ``"err"``, ``"skipped"`` or ``"aborted"`` (the
            run was cancelled while the knot held its slot); ``None`` on
            admit.
        gate: The run's gate, so an observer can adjust a limit in reaction.
    """

    kind: str
    run_id: str
    knot_id: str
    group: str | None
    in_flight: int
    group_in_flight: int
    max_in_flight: int | None
    group_limit: int | None
    waiting: int
    queued_seconds: float
    held_seconds: float | None
    outcome: str | None
    gate: Admission = field(repr=False, compare=False)
