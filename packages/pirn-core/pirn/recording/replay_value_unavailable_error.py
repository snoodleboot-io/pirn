"""Raised when a recorded output hash has no value left in the ``DataStore``."""

from __future__ import annotations

from pirn.recording.replay_error import ReplayError


class ReplayValueUnavailableError(ReplayError):
    """The lineage row is intact but the value it points at is gone.

    Lineage and data have deliberately different lifetimes: ``KnotLineage``
    rows are retained indefinitely while the ``DataStore`` they reference can
    be scrubbed once a value passes its TTL, or evicted by a bounded backend
    that declared a ``max_values`` ceiling in its
    :attr:`~pirn.backends.base.data_store.DataStore.retention` (PIR-839).
    That split is what makes retention policy expressible at all, and it means
    a run can be perfectly described by history and still be unreplayable.

    Replay reports that as its own condition rather than as a mismatch —
    nothing about the computation changed, the bytes are simply no longer
    there — and never falls back to executing the knot.

    Attributes:
        knot_id: The knot whose recorded output could not be read.
        source_run_id: The run the replay is reading from.
        output_hash: The content hash that is absent from the store.
        detail: What the store said about the absence, when it knew.
    """

    def __init__(
        self,
        *,
        knot_id: str,
        source_run_id: str,
        output_hash: str,
        detail: str | None = None,
    ) -> None:
        """Report a recorded value that the data store can no longer produce.

        Args:
            knot_id: The knot whose recorded output could not be read.
            source_run_id: The run being replayed.
            output_hash: The content hash the lineage row names.
            detail: The store's own account of the absence — a bounded store
                knows it evicted the value and says so.  When ``None``, the
                message falls back to naming the possibilities.
        """
        cause = (
            detail
            if detail is not None
            else (
                "The value was scrubbed past its TTL, or this run is reading a "
                "different DataStore than the one the recording wrote to."
            )
        )
        super().__init__(
            f"replay of knot {knot_id!r} against run {source_run_id!r}: lineage "
            f"records output hash {output_hash!r} but no value is stored under it. "
            f"{cause}"
        )
        self._knot_id = knot_id
        self._source_run_id = source_run_id
        self._output_hash = output_hash
        self._detail = detail

    @property
    def knot_id(self) -> str:
        return self._knot_id

    @property
    def source_run_id(self) -> str:
        return self._source_run_id

    @property
    def output_hash(self) -> str:
        return self._output_hash

    @property
    def detail(self) -> str | None:
        return self._detail
