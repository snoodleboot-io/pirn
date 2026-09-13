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
    at all can start.  The ready queue keeps one FIFO per concurrency group
    and offers their heads in readiness order, so a head refused because its
    group is full does not stop knots of other groups from being offered;
    only the knots queued behind it in its own group wait (design §6).

    A gate must refuse only for reasons shared by the knot's whole group --
    its group's budget or the run's -- because the queue passes over the
    rest of a refused head's group.  With run-wide capacity available
    (``has_capacity``), a refusal means the group is full: the queue parks
    that group and offers it again only once a slot of the group is released
    (the engine tells the queue, using ``AdmissionTicket.group``).

    Implementations inherit and override every method.
    """

    def has_capacity(self) -> bool:
        """Whether the run-wide budget could admit any knot at all.

        The ready queue asks this before offering anything, so a full run
        costs one call per admission attempt rather than one refusal per
        queued group.  ``True`` does not promise ``try_admit`` succeeds: the
        knot's own group may still be full.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement has_capacity()")

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
