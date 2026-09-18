"""The default gate: every ready knot starts immediately."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pirn.engine.admission.admission import Admission
from pirn.engine.admission.admission_limit_error import AdmissionLimitError
from pirn.engine.admission.admission_ticket import AdmissionTicket

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class UnboundedAdmission(Admission):
    """Admits every knot, holding no lock and no counter.

    This is the engine's default, so a run with no concurrency limit pays for
    admission only the cost of building a ticket.
    """

    def has_capacity(self) -> bool:
        """Always ``True``: nothing is ever held."""
        return True

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

    def check_group(self, knot: Knot) -> None:
        """Accept every knot: this gate defines no groups, so every tag is ignored.

        Args:
            knot: A knot this gate may be asked to admit.
        """

    async def wait_for_release(self) -> None:
        """Return at once.

        ``try_admit`` never refuses, so there is never a reason to wait; the
        method returns rather than hanging should a caller ask anyway.
        """

    def current_limit(self, group: str | None) -> int | None:
        """Always ``None``: no budget is bounded."""
        return None

    def set_limit(self, group: str | None, limit: int) -> None:
        """Refuse: this gate enforces nothing, so there is nothing to adjust.

        Raises:
            AdmissionLimitError: Always.  Start the run with
                ``ConcurrencyLimits`` to get a gate whose caps can move.
        """
        raise AdmissionLimitError(
            "the unbounded gate enforces no limits; run with ConcurrencyLimits "
            "to adjust a cap at runtime"
        )
