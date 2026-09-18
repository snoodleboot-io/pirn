"""Interface for deciding when a ready knot may start executing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.engine.admission.admission_ticket import AdmissionTicket


class Admission:
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

    A gate's limits may be adjusted while the run is live (``set_limit``,
    ADR agents-speaks-core WS0): the new cap applies to every admission from
    then on and never touches a ticket already issued, so an adaptive
    controller -- an ``AdmissionObserver`` reacting to throttled outcomes or
    a growing queue -- can steer the run without stopping it.

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

    def check_group(self, knot: Knot) -> None:
        """Refuse, before anything is taken, a knot whose group this gate can never admit.

        The engine calls this for every knot of the static graph at run start,
        so a misnamed ``concurrency_group`` fails the run before any knot
        starts; a gate that composes others (``ChainedAdmission``) calls it on
        each of them before taking a ticket from any, so the check never
        leaves a slot behind.

        Args:
            knot: A knot this gate may be asked to admit.

        Raises:
            UndefinedConcurrencyGroupError: If the gate's limits define
                groups and *knot*'s group is not one of them.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement check_group()")

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

    def current_limit(self, group: str | None) -> int | None:
        """Return the cap in force for *group* right now.

        Args:
            group: A concurrency group, or ``None`` for the run-wide cap.

        Returns:
            The cap, or ``None`` when that budget is unbounded.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement current_limit()")

    def set_limit(self, group: str | None, limit: int) -> None:
        """Change the cap for *group* for every admission from now on.

        Tickets already issued are untouched: lowering a cap below what is
        in flight simply refuses new admissions until enough slots come
        back, and raising it lets the next release admit more.

        Args:
            group: A group the run's limits define, or ``None`` for the
                run-wide cap.
            limit: The new cap; at least 1.

        Raises:
            AdmissionLimitError: If the gate enforces no limits, *group* is
                not one it defines, or *limit* is below 1.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement set_limit()")
