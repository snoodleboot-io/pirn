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

    It carries only the knot id today, because the one gate that exists
    (``UnboundedAdmissionGate``) holds no capacity.  A bounded gate records the
    slots it took here, so that releasing a ticket frees exactly what admitting
    it claimed (PIR-841).

    Attributes:
        knot_id: The id of the admitted knot.
    """

    knot_id: str
