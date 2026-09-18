"""Raised when a knot that registers successors mid-run has no extensible run to register into."""

from __future__ import annotations

from pirn.exceptions.tapestry_error import TapestryError


class ExtensibleRunRequiredError(TapestryError):
    """A knot whose whole purpose is to spawn successors ran outside an extensible run.

    ``WithContinuation`` calls its continuation and registers whatever it
    returns into the running tapestry's store (``Tapestry.current_store()``,
    ``None`` outside an extensible run).  It used to return its input unchanged
    when the store was absent, so a continuation attached inside a plain
    ``tapestry.run(...)`` ran, produced its successors, and had every one of
    them dropped -- a pipeline that silently executed a prefix of itself and
    reported success.  Nothing downstream could tell that apart from a
    continuation that legitimately ended the flow.

    Raised instead, so the wiring mistake is the knot's ``Err`` (PIR-873).

    Attributes:
        knot_id: The knot that had nowhere to register its successors.
    """

    def __init__(self, *, knot_class: str, knot_id: str) -> None:
        """Name the knot and what it needed.

        Args:
            knot_class: ``type(knot).__name__``.
            knot_id: The knot's id.
        """
        self._knot_id = knot_id
        super().__init__(
            f"{knot_class}({knot_id!r}): no extensible run is active, so the "
            "successors the continuation returned have nowhere to go.  Start "
            "the run with an extensible inner tapestry (a SubTapestry whose "
            "_extensible_inner_run is True, e.g. LoopSubTapestry) or drop the "
            "continuation."
        )

    @property
    def knot_id(self) -> str:
        """The knot that had nowhere to register its successors."""
        return self._knot_id
