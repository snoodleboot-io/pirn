"""``StampBronzeMetadataKnot`` — append ``ingested_at`` UTC timestamp and
``source_uri`` to every row in the upstream batch.

Used by :class:`BronzeRawIngest`. ``source_uri`` is held as instance
state. The original row tuple is concatenated with two new values so
the downstream ``DatabaseExecuteSink`` can use a single positional-
binding INSERT.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class StampBronzeMetadataKnot(Knot):
    """Append ``ingested_at`` + ``source_uri`` columns to every row."""

    def __init__(
        self,
        *,
        rows: Knot,
        source_uri: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_uri, str) or not source_uri:
            raise ValueError(
                "StampBronzeMetadataKnot: source_uri must be a non-empty string"
            )
        self._source_uri = source_uri
        super().__init__(rows=rows, _config=_config, **kwargs)

    async def process(
        self, rows: Iterable[Iterable[Any]], **_: Any
    ) -> list[tuple[Any, ...]]:
        """Append the current UTC timestamp and source_uri to every row and return the stamped list.

        Args:
            rows: The upstream rows to stamp; each row is itself an iterable of values.

        Returns:
            A list of tuples with the original values followed by ingested_at and source_uri.
        """
        ingested_at = datetime.now(timezone.utc).isoformat()
        return [tuple(row) + (ingested_at, self._source_uri) for row in rows]
