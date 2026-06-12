"""``StampBronzeMetadataKnot`` — append ``ingested_at`` UTC timestamp and
``source_uri`` to every row in the upstream batch.

Used by :class:`BronzeRawIngest`.  Both ``source_uri`` and the row list
arrive as resolved values in ``process()``.  The original row tuple is
concatenated with two new values so the downstream
``DatabaseExecuteSink`` can use a single positional-binding INSERT.

Algorithm:
    1. Receive ``rows`` and ``source_uri`` in ``process()``.
    2. Validate that ``source_uri`` is a non-empty string.
    3. Capture the current UTC timestamp as an ISO-8601 string.
    4. For each row, concatenate the row tuple with ``(ingested_at, source_uri)``.
    5. Return the list of stamped tuples.

References:
    [1] pirn — BronzeRawIngest:
        pirn/domains/data/specializations/medallion/bronze_raw_ingest.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class StampBronzeMetadataKnot(Knot):
    """Append ``ingested_at`` + ``source_uri`` columns to every row."""

    def __init__(
        self,
        *,
        rows: Knot,
        source_uri: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(rows=rows, source_uri=source_uri, _config=_config, **kwargs)

    async def process(
        self,
        *,
        rows: Any,
        source_uri: Any,
        **_: Any,
    ) -> list[tuple[Any, ...]]:
        """Validate source_uri, stamp each row with metadata, and return the list.

        Args:
            rows: Upstream rows to stamp; each row is an iterable of values.
            source_uri: The source URI string to append to every row.

        Returns:
            A list of tuples with the original values followed by ingested_at and source_uri.

        Raises:
            ValueError: If ``source_uri`` is empty or not a string.
        """
        if not isinstance(source_uri, str) or not source_uri:
            raise ValueError("StampBronzeMetadataKnot: source_uri must be a non-empty string")
        ingested_at = datetime.now(UTC).isoformat()
        return [(*tuple(row), ingested_at, source_uri) for row in rows]
