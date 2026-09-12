"""The default gate: every ready knot starts immediately."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pirn.engine.admission.admission_gate import AdmissionGate
from pirn.engine.admission.admission_ticket import AdmissionTicket

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class UnboundedAdmissionGate(AdmissionGate):
    """Admits every knot, holding no lock and no counter.

    This is the engine's default, so a run with no concurrency limit pays for
    admission only the cost of building a ticket.
    """

    def try_admit(self, knot: Knot) -> AdmissionTicket:
        """Admit *knot* unconditionally.

        Args:
            knot: The ready knot asking to start.

        Returns:
            A ticket for *knot*.  Never ``None``.
        """
        return AdmissionTicket(knot_id=knot.knot_id)

    def release(self, ticket: AdmissionTicket) -> None:
        """Accept *ticket* back.  Nothing was held, so nothing is freed.

        Args:
            ticket: A ticket this gate issued.
        """

    async def wait_for_release(self) -> None:
        """Return at once.

        ``try_admit`` never refuses, so there is never a reason to wait; the
        method returns rather than hanging should a caller ask anyway.
        """
