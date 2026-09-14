"""``_AdmissionSlotKnot`` — a token knot letting a bare gate meter non-graph code.

Algorithm:
    ``AdmissionGate.try_admit``/``release`` (``pirn.engine.admission``) read
    only ``knot.config.concurrency_group`` and ``knot.knot_id`` from the
    knot they are given; they never dispatch it. One instance is built per
    pool (:class:`~pirn_agents.performance._backpressure_gate._BackpressureGate`)
    and reused for every ``try_admit`` call: ticket identity comes from the
    ``AdmissionTicket`` object the gate constructs and returns fresh each
    time, not from the knot passed in, so reusing one token is safe even
    for many overlapping, concurrent acquisitions -- core's own
    ``tests/unit/engine/admission/test_limited_admission_gate_shared.py``
    establishes exactly the same pattern with its ``_Noop`` knot.

    ``process()`` is never invoked: this knot is built outside any
    ``Tapestry`` run (``Knot.__init__`` only self-registers with an *active*
    tapestry, and none is open here), purely so its ``config``/``knot_id``
    can be handed to the engine's own admission machinery.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot


class _AdmissionSlotKnot(Knot):
    """A knot built only for its identity; never dispatched by an engine."""

    async def process(self, **_: Any) -> None:
        """Never invoked -- see the module docstring."""
        return None
