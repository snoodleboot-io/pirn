"""``_EndKnot`` — built-in terminal knot registered when a continuation returns ``Next('end')``."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot


class _EndKnot(Knot):
    """Terminal knot — registered when a continuation returns Next('end').

    Produces no output.  Its presence in the graph makes explicit that the
    flow terminated intentionally at this point, not due to an error or
    missing logic.
    """

    async def process(self, **_: Any) -> None:
        """Receive any inputs and return None to mark explicit flow termination.

        Returns:
            None, signalling that this branch of the flow has terminated intentionally.
        """
        return None
