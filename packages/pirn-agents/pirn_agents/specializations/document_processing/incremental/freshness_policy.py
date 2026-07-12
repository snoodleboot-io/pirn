"""``FreshnessPolicy`` — TTL/staleness policy for indexed content (F25-S4 / PIR-626).

A small, backend-free policy object the pipeline consults to decide whether an
already-indexed document has aged past its time-to-live and should be re-fetched
and re-indexed. Re-indexing a stale-but-unchanged document is cheap because the
upsert-by-hash path (F25-S4) re-embeds nothing and merely refreshes the
manifest timestamp, resetting the TTL clock.
"""

from __future__ import annotations

from collections.abc import Mapping


class FreshnessPolicy:
    """Flag content whose age exceeds a fixed time-to-live."""

    def __init__(self, *, ttl_seconds: float) -> None:
        """Configure the time-to-live.

        Args:
            ttl_seconds: Maximum age in seconds before content is stale. Must be
                positive.

        Raises:
            ValueError: If ``ttl_seconds`` is not positive.
        """
        if ttl_seconds <= 0:
            raise ValueError(f"FreshnessPolicy: ttl_seconds must be positive, got {ttl_seconds!r}")
        self._ttl_seconds = ttl_seconds

    def age_seconds(self, indexed_at: float, now: float) -> float:
        """Return the age in seconds of content indexed at ``indexed_at``."""
        return now - indexed_at

    def is_stale(self, indexed_at: float, now: float) -> bool:
        """Return whether content indexed at ``indexed_at`` is stale at ``now``.

        Args:
            indexed_at: Epoch seconds when the content was last indexed.
            now: The current epoch seconds.

        Returns:
            ``True`` when the age strictly exceeds ``ttl_seconds``.
        """
        return (now - indexed_at) > self._ttl_seconds

    def stale_documents(self, indexed_at_by_doc: Mapping[str, float], now: float) -> list[str]:
        """Return the ids of documents whose last-indexed time is stale.

        Args:
            indexed_at_by_doc: Map of document id to its last-indexed epoch time.
            now: The current epoch seconds.

        Returns:
            Sorted document ids whose content is stale and should be refreshed.
        """
        return sorted(
            doc_id
            for doc_id, indexed_at in indexed_at_by_doc.items()
            if self.is_stale(indexed_at, now)
        )
