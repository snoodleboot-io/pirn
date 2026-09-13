"""The record of one knot's admission into a run."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdmissionTicket:
    """Proof that an ``AdmissionGate`` admitted a knot, handed back on release.

    The ticket is the lifecycle boundary of a single execution: it is issued
    when the gate lets a knot start and returned to the same gate when the knot
    stops holding capacity, whether it ran, was skipped, or failed.  Anything
    that must happen *while a knot occupies capacity* -- a future per-call
    timeout, or a retry that gives its slot back during backoff -- wraps the
    ticket rather than the dispatch call, so it measures run time and never
    queue time.

    A ticket records the slots its admission took, so that releasing it frees
    exactly what admitting it claimed (PIR-841).

    Attributes:
        knot_id: The id of the admitted knot.
        group: The concurrency group whose limited slot the knot holds, or
            ``None`` when it holds no group slot: the knot has no group, or
            the gate does not limit that group.
    """

    knot_id: str
    group: str | None = None
