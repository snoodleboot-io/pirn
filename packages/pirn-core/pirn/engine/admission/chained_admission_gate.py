"""A gate that admits only when both a child budget and its parent's have room."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from pirn.engine.admission.admission_gate import AdmissionGate
from pirn.engine.admission.admission_release_error import AdmissionReleaseError
from pirn.engine.admission.admission_ticket import AdmissionTicket

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class ChainedAdmissionGate(AdmissionGate):
    """Admits a knot only when both an *own* gate and a *parent* gate admit it.

    An inner run that declares its own ``ConcurrencyLimits`` under an
    enclosing run must still respect the enclosing run's budget.  Before this
    class, an inner run with its own limits got a gate built from
    ``Engine.gate_for(own_limits)`` alone -- entirely unrelated to the
    enclosing run's gate -- so its leaves ran under their own cap *in
    addition to* whatever the enclosing run already had in flight, with no
    shared ceiling at all.  ``ChainedAdmissionGate`` fixes that by requiring
    a ticket from both the *own* gate (this run's declared limits) and the
    *parent* gate (the enclosing run's -- itself possibly another chain
    further up the tree) before admitting, and releasing both together.

    Algorithm:
        ``try_admit(knot)``:

        1. Ask the own gate for a ticket.  Refused -> refuse; nothing was
           taken from the parent.
        2. Ask the parent gate for a ticket for the same knot.  Refused ->
           give the own ticket back and refuse.  Admission is all-or-nothing
           across both budgets, the same all-or-nothing shape
           ``LimitedAdmissionGate`` already uses across its own global and
           group budgets.
        3. Both admitted -> wrap them in one combined ticket, remember the
           pair by the combined ticket's identity, and return it.

        ``release(ticket)``: look up the pair the combined ticket stands
        for, release the parent ticket and then the own ticket.

        ``has_capacity()``: both gates must report capacity.

        ``wait_for_release()``: wait for a release from either gate,
        whichever comes first.

    Group semantics (``AdmissionTicket.group``) are the *own* gate's alone.
    The parent gate is asked to admit the very same ``Knot``, so if the
    enclosing run's limits define groups of their own and this knot's
    ``concurrency_group`` happens to collide with one of them, the parent
    applies its own group accounting too -- a knot can be validated against
    the *own* limits at run start (``Engine._check_groups``) yet still be
    refused, or raise ``UndefinedConcurrencyGroupError``, from the parent's
    side of this chain.  That cross-level group validation is not solved
    here; this class fixes the ``max_in_flight`` / global-budget defect
    (PIR-870) that motivated it.  The combined ticket surfaces the *own*
    gate's group because that is what this run's own ``ReadyQueue.unpark``
    and ``AdmissionFeedback`` key their bookkeeping on.

    Threading: delegates every counter to the wrapped gates, which are
    already safe to call from several loops/threads at once
    (``LimitedAdmissionGate``).  Only the pair bookkeeping here needs its
    own lock.
    """

    def __init__(self, *, own: AdmissionGate, parent: AdmissionGate) -> None:
        """Build a gate that chains *own* under *parent*.

        Args:
            own: The gate built from this run's own ``ConcurrencyLimits``.
            parent: The enclosing run's gate -- shared by identity with
                every other run in the tree that inherits it, and possibly
                itself a ``ChainedAdmissionGate`` further up the tree.
        """
        self._own = own
        self._parent = parent
        self._pairs: dict[int, tuple[AdmissionTicket, AdmissionTicket]] = {}
        self._lock = threading.Lock()

    def has_capacity(self) -> bool:
        """Whether both the own and the parent budget could admit a knot."""
        return self._own.has_capacity() and self._parent.has_capacity()

    def try_admit(self, knot: Knot) -> AdmissionTicket | None:
        """Admit *knot* only if both the own and the parent gate admit it.

        Args:
            knot: The ready knot asking to start.

        Returns:
            A combined ticket, or ``None`` if either gate refused -- in
            which case whichever gate did admit has already had its ticket
            given back, so this chain holds nothing while the knot waits.
        """
        own_ticket = self._own.try_admit(knot)
        if own_ticket is None:
            return None
        parent_ticket = self._parent.try_admit(knot)
        if parent_ticket is None:
            self._own.release(own_ticket)
            return None
        combined = AdmissionTicket(knot_id=knot.knot_id, group=own_ticket.group)
        with self._lock:
            self._pairs[id(combined)] = (own_ticket, parent_ticket)
        return combined

    def release(self, ticket: AdmissionTicket) -> None:
        """Release both underlying tickets *ticket* stands for, together.

        Args:
            ticket: A combined ticket this gate issued.

        Raises:
            AdmissionReleaseError: If this gate is not holding *ticket*.
        """
        with self._lock:
            pair = self._pairs.pop(id(ticket), None)
        if pair is None:
            raise AdmissionReleaseError(
                f"knot {ticket.knot_id!r} holds no slot in this chained gate; "
                "its ticket was released already or was issued elsewhere"
            )
        own_ticket, parent_ticket = pair
        self._parent.release(parent_ticket)
        self._own.release(own_ticket)

    async def wait_for_release(self) -> None:
        """Suspend until either the own or the parent gate reports a release."""
        own_wait = asyncio.ensure_future(self._own.wait_for_release())
        parent_wait = asyncio.ensure_future(self._parent.wait_for_release())
        try:
            await asyncio.wait({own_wait, parent_wait}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for pending in (own_wait, parent_wait):
                if not pending.done():
                    pending.cancel()
            await asyncio.gather(own_wait, parent_wait, return_exceptions=True)

    def current_limit(self, group: str | None) -> int | None:
        """The own gate's live cap for *group*.

        The parent's cap belongs to the enclosing run and is not this
        chain's to report; a caller wanting the tree-wide cap reads it off
        the enclosing run's own plane.
        """
        return self._own.current_limit(group)

    def set_limit(self, group: str | None, limit: int) -> None:
        """Adjust the own gate's cap for *group*.

        The parent gate's cap belongs to the enclosing run and is never
        adjusted from here.

        Raises:
            AdmissionLimitError: Delegated from the own gate -- e.g. if it
                enforces no limits, or does not define *group*.
        """
        self._own.set_limit(group, limit)
