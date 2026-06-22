"""``ScadaDatabaseAssembler`` — assemble a :class:`ScadaPayload` from historian rows.

Sits between :class:`~pirn.connectors.knots.database_query_source.DatabaseQuerySource`
(which produces ``list[tuple]``) and downstream SCADA knots that consume
:class:`~pirn_oilgas.types.scada_payload.ScadaPayload`.

Each row must be a ``(timestamp, value)`` pair. The assembler converts the
value column into a float64 numpy array and constructs the typed payload.

References:
    - OPC Foundation (2017). OPC Unified Architecture Specification, Part 11
      — Historical Access.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.scada_payload import ScadaPayload
from pirn_oilgas.types.scada_time_series import ScadaTimeSeries


class ScadaDatabaseAssembler(Assembler):
    """Assemble a :class:`ScadaPayload` from historian query rows."""

    def __init__(
        self,
        *,
        rows: Knot,
        tag: Knot | str,
        since: Knot | datetime,
        sample_interval_sec: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            tag=tag,
            since=since,
            sample_interval_sec=sample_interval_sec,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        rows: list[tuple[Any, ...]],
        tag: str,
        since: datetime,
        sample_interval_sec: float,
        **_: Any,
    ) -> ScadaPayload:
        """Convert historian rows into a :class:`ScadaPayload`.

        Args:
            rows: List of ``(timestamp, value)`` tuples from a historian query.
            tag: Non-empty tag name string used as ``sensor_id``.
            since: Datetime from which the historian data was retrieved.
            sample_interval_sec: Positive sample interval in seconds.

        Returns:
            :class:`ScadaPayload` with float64 sample values extracted from
            the value column of each row.

        Raises:
            TypeError: If ``rows`` is not a list, ``tag`` is not a str, ``since``
                is not a datetime, or ``sample_interval_sec`` is not numeric.
            ValueError: If ``tag`` is empty or ``sample_interval_sec`` is not positive.
        """
        if not isinstance(rows, list):
            raise TypeError(f"ScadaDatabaseAssembler: rows must be list, got {type(rows).__name__}")
        if not isinstance(tag, str):
            raise TypeError(f"ScadaDatabaseAssembler: tag must be str, got {type(tag).__name__}")
        if not tag:
            raise ValueError("ScadaDatabaseAssembler: tag must be non-empty")
        if not isinstance(since, datetime):
            raise TypeError(
                f"ScadaDatabaseAssembler: since must be datetime, got {type(since).__name__}"
            )
        if not isinstance(sample_interval_sec, (int, float)):
            raise TypeError(
                "ScadaDatabaseAssembler: sample_interval_sec must be numeric, "
                f"got {type(sample_interval_sec).__name__}"
            )
        if sample_interval_sec <= 0.0:
            raise ValueError("ScadaDatabaseAssembler: sample_interval_sec must be positive")
        values = np.array([float(row[1]) for row in rows], dtype=np.float64)
        return ScadaPayload(
            metadata=ScadaTimeSeries(
                sensor_id=tag,
                sample_count=len(values),
                sample_interval_sec=float(sample_interval_sec),
            ),
            data=values,
        )
