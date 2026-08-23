"""Raised when the recording does not describe the computation being replayed."""

from __future__ import annotations

from pirn.recording.replay_error import ReplayError


class ReplayMismatchError(ReplayError):
    """The recorded run does not describe the knot invocation being replayed.

    Raised when the source run has no row for a knot the current run reached,
    or when it has one whose invocation identity disagrees — a different knot
    configuration, different parent input hashes, or different literal
    constructor arguments.

    This is the guard that keeps replay honest.  A replayed knot is not
    executed, so nothing else would notice that the graph, its parameters or
    its wiring had moved on since the recording; the served value would simply
    be stale and wrong, with a plausible-looking lineage row to match.

    Attributes:
        knot_id: The knot whose invocation could not be matched.
        source_run_id: The run the replay is reading from.
        reason: Which component of the invocation identity disagreed.
    """

    def __init__(self, *, knot_id: str, source_run_id: str, reason: str) -> None:
        super().__init__(
            f"replay of knot {knot_id!r} against run {source_run_id!r}: {reason}. "
            "Replay refuses to execute the knot instead — re-run without "
            "`replay=` if live execution is what you want."
        )
        self._knot_id = knot_id
        self._source_run_id = source_run_id
        self._reason = reason

    @property
    def knot_id(self) -> str:
        return self._knot_id

    @property
    def source_run_id(self) -> str:
        return self._source_run_id

    @property
    def reason(self) -> str:
        return self._reason
