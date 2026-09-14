"""The record of one knot's admission into a run."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdmissionTicket:
    """Proof that an ``AdmissionGate`` admitted a knot, handed back on release.

    The ticket is the lifecycle boundary of a single execution: it is issued
    when the gate lets a knot start and returned to the same gate when the knot
    stops holding capacity, whether it ran, was skipped, or failed.  A knot's
    ``KnotConfig.timeout`` and ``retry`` run inside that boundary
    (``GovernedDispatch``): the slot is held for each attempt, so the timeout
    measures run time and never queue time, but it is released for the
    backoff sleep *between* attempts and re-admitted before the next one
    (PIR-870) -- a sleeping retry does not hold capacity another ready knot
    could use.  The ticket a knot's task ends with may therefore differ, by
    identity, from the one it was admitted with; ``AdmissionTicketHolder`` is
    what the engine reads back to find out which one is current.

    A ticket records the slots its admission took, so that releasing it frees
    exactly what admitting it claimed (PIR-841).

    A *container* knot — a ``SubTapestry``, a ``LoopSubTapestry``, a loop
    iteration — holds no slot at all (``Knot._holds_admission_slot`` is
    ``False``): it spends its life waiting on an inner run whose leaves are
    admitted individually through the same gate, so a slot held by the
    container would be a slot its own leaves could deadlock on.  Such a knot is
    admitted without consulting the gate and gets a ticket with ``held`` set
    to ``False``, which the engine never hands back to the gate (ADR
    agents-speaks-core, WS0b; PIR-841 design §5.4).

    Attributes:
        knot_id: The id of the admitted knot.
        group: The concurrency group whose limited slot the knot holds, or
            ``None`` when it holds no group slot: the knot has no group, or
            the gate does not limit that group.
        held: Whether the gate holds capacity for this ticket.  ``True`` for
            every ticket a gate issues; ``False`` for the slot-free ticket
            the ready queue issues a container knot.
    """

    knot_id: str
    group: str | None = None
    held: bool = True
