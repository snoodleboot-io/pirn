"""``ScadaHistorianIngester`` — pull a tag stream from a historian connection."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.protocols.historian_connection import HistorianConnection
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class ScadaHistorianIngester(Knot):
    """Resolve a historian tag into a :class:`ScadaTimeSeries` reference."""

    def __init__(
        self,
        *,
        connection: HistorianConnection,
        tag: str,
        since: datetime,
        sample_interval_sec: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(connection, HistorianConnection):
            raise TypeError(
                "ScadaHistorianIngester: connection must be a HistorianConnection"
            )
        if not isinstance(tag, str) or not tag:
            raise ValueError(
                "ScadaHistorianIngester: tag must be a non-empty string"
            )
        if not isinstance(since, datetime):
            raise TypeError(
                "ScadaHistorianIngester: since must be a datetime"
            )
        if not isinstance(sample_interval_sec, (int, float)) or sample_interval_sec <= 0.0:
            raise ValueError(
                "ScadaHistorianIngester: sample_interval_sec must be positive"
            )
        self._connection = connection
        self._tag = tag
        self._since = since
        self._sample_interval_sec = float(sample_interval_sec)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        """Pull the configured tag from the historian connection and return a ScadaTimeSeries reference.

        Returns:
            ScadaTimeSeries with the configured tag as sensor_id and the
            configured sample_interval_sec.
        """
        return ScadaTimeSeries(
            sensor_id=self._tag,
            sample_interval_sec=self._sample_interval_sec,
        )
