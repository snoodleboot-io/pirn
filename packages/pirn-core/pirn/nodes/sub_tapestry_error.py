"""``SubTapestryError`` — raised when a ``SubTapestry``'s inner tapestry pipeline fails."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pirn.exceptions.pirn_error import PirnError

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class SubTapestryError(PirnError):
    """Raised when the inner tapestry pipeline fails.

    Attached to the ``Err`` the outer pipeline receives so the inner
    ``RunResult`` is reachable for inspection.
    """

    def __init__(self, inner_result: RunResult) -> None:
        self.inner_result = inner_result
        exception_count = len(inner_result.exceptions)
        causes = "; ".join(
            f"{record.knot_id}: {record.exc_type}: {record.message}"
            for record in inner_result.exceptions
        )
        super().__init__(
            f"inner pipeline failed with {exception_count} exception(s); "
            f"run_id={inner_result.run_id!r}" + (f" [{causes}]" if causes else "")
        )
