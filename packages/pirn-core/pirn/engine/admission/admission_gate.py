"""Interface for deciding when a ready knot may start executing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.engine.admission.admission_ticket import AdmissionTicket


class AdmissionGate:
    """Interface: admits ready knots into a run while capacity allows.

    The engine keeps knots whose parents have all resolved in a ready queue
    and offers them to the run's gate one at a time.  A knot is decided,
    materialized and dispatched only once the gate admits it, so a knot the
    gate refuses costs nothing while it waits: no input reads, no task.

    Admission is non-blocking by design: ``try_admit`` answers immediately,
    and ``wait_for_release`` is the one place a scheduler parks when nothing
    at all can start.  Today the ready queue is a single FIFO, so a refused
    head stops admission until capacity frees up; nothing queued behind it is
    offered in the meantime.

    TODO(PIR-841 slice 2): keep one FIFO per concurrency group (design §6) so
    a refused head in a saturated group does not block ready knots in other
    groups.

    Implementations inherit and override every method.
    """

    def try_admit(self, knot: Knot) -> AdmissionTicket | None:
        """Admit *knot* if capacity allows.

        Args:
            knot: The ready knot asking to start.

        Returns:
            A ticket the caller must hand back to ``release`` once the knot no
            longer holds capacity, or ``None`` if the knot must keep waiting.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement try_admit()")

    def release(self, ticket: AdmissionTicket) -> None:
        """Return the capacity *ticket* holds to the gate.

        Args:
            ticket: A ticket this gate issued and that has not been released.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement release()")

    async def wait_for_release(self) -> None:
        """Suspend until capacity may have been freed.

        Called only after ``try_admit`` refused a knot and nothing the caller
        is running could free capacity on completion.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement wait_for_release()")
