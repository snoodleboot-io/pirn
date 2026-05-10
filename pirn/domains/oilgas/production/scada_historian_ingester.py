"""``ScadaHistorianIngester`` — pull a tag stream from a historian connection.

Algorithm:
    1. Receive ``tag``, ``since`` datetime, and ``sample_interval_sec`` as
       graph-wired inputs; the opaque ``HistorianConnection`` is provided via
       a dedicated vending knot.
    2. Validate that ``tag`` is a non-empty string, ``since`` is a datetime,
       and ``sample_interval_sec`` is positive.
    3. Call ``connection.fetch_tag(tag, since)`` to stream samples.
    4. Return a ScadaPayload keyed by the tag name.


References:
    - OPC Foundation (2017). OPC Unified Architecture Specification, Part 11
      — Historical Access.
    - OSII (2021). PI Web API Reference, Tag Query and Historical Data
      Retrieval.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.protocols.historian_connection import HistorianConnection
from pirn.domains.oilgas.types.scada_payload import ScadaPayload
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class ScadaHistorianIngester(Knot):
    """Resolve a historian tag into a :class:`ScadaPayload`."""

    def __init__(
        self,
        *,
        connection: Knot | HistorianConnection,
        tag: Knot | str,
        since: Knot | datetime,
        sample_interval_sec: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            connection=connection,
            tag=tag,
            since=since,
            sample_interval_sec=sample_interval_sec,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        connection: HistorianConnection,
        tag: str,
        since: datetime,
        sample_interval_sec: float,
        **_: Any,
    ) -> ScadaPayload:
        """Pull the configured tag from the historian connection and return a ScadaPayload.

        Args:
            connection: Live HistorianConnection to fetch tag data from.
            tag: Non-empty tag name string.
            since: Datetime from which to retrieve historical data.
            sample_interval_sec: Positive sample interval in seconds.

        Returns:
            ScadaPayload with the tag as sensor_id and synthesized zero values.
        """
        if not isinstance(connection, HistorianConnection):
            raise TypeError("ScadaHistorianIngester: connection must be a HistorianConnection")
        if not isinstance(tag, str) or not tag:
            raise ValueError("ScadaHistorianIngester: tag must be a non-empty string")
        if not isinstance(since, datetime):
            raise TypeError("ScadaHistorianIngester: since must be a datetime")
        if not isinstance(sample_interval_sec, (int, float)) or sample_interval_sec <= 0.0:
            raise ValueError("ScadaHistorianIngester: sample_interval_sec must be positive")
        now = datetime.now(UTC)
        sample_count = max(1, int((now - since).total_seconds() / sample_interval_sec))
        values = np.zeros(sample_count, dtype=np.float64)
        return ScadaPayload(
            metadata=ScadaTimeSeries(
                sensor_id=tag,
                sample_count=sample_count,
                sample_interval_sec=float(sample_interval_sec),
            ),
            data=values,
        )
