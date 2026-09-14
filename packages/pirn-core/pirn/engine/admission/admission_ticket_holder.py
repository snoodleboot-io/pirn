"""A mutable slot for the ticket currently backing one dispatched knot's admission."""

from __future__ import annotations

from pirn.engine.admission.admission_ticket import AdmissionTicket


class AdmissionTicketHolder:
    """Tracks whichever ``AdmissionTicket`` currently backs one in-flight knot.

    ``GovernedDispatch`` swaps the ticket a retrying knot holds: released
    before the backoff sleep and replaced by a freshly admitted one before
    the next attempt, so a sleeping retry does not hold a slot another knot
    could use (PIR-870; see ``AdmissionTicket`` and ``GovernedDispatch`` for
    why this used to be a known limitation). The ticket a gate issues is
    immutable and identity-tracked, so the *holder* is what lets the engine
    ask "whichever ticket is current" once the knot's task completes and
    release exactly that one, rather than the one it started with.
    """

    def __init__(self, ticket: AdmissionTicket) -> None:
        """Start the holder off with the ticket the engine admitted the knot with.

        Args:
            ticket: The ticket issued at admission, before the knot's task
                is even created.
        """
        self.ticket = ticket
