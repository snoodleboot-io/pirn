"""``LagFeatureGenerator`` — generate ``<column>_lag_<N>`` features for
time-series datasets.

For every requested ``(column, lag)`` pair the pipeline appends a new
feature name to each partition of the upstream :class:`SplitManifest`. The
orchestration layer only updates the feature-name catalogue; concrete
subclasses are responsible for the row-level shifting that materialises
the lag values, ordered by the configured ``time_column``.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``time_column``, ``columns``, and
       ``lags`` via process().
    2. Validate all inputs.
    3. Wire _LagAppendKnot in an inner Tapestry.
    4. Run via _run_inner() and return the extended SplitManifest.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.specializations.feature_engineering._lag_append_knot import (
    _LagAppendKnot,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class LagFeatureGenerator(SubTapestry):
    """Append per-(column, lag) features to a time-series :class:`SplitManifest`."""

    def __init__(
        self,
        *,
        split: Knot,
        time_column: Knot | str,
        columns: Knot | Sequence[str],
        lags: Knot | Sequence[int] = (1, 7),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            time_column=time_column,
            columns=columns,
            lags=lags,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        time_column: str = "",
        columns: Sequence[str] = (),
        lags: Sequence[int] = (1, 7),
        **_: Any,
    ) -> SplitManifest:
        """Append lag feature names for each (column, lag) pair to every partition and return the extended SplitManifest.

        Args:
            split: SplitManifest whose partitions receive the new lag feature names.
            time_column: Non-empty time ordering column name.
            columns: Non-empty sequence of column names to lag.
            lags: Non-empty sequence of lag integers; each must be >= 1.

        Returns:
            SplitManifest with ``<column>_lag_<N>`` feature names appended to every partition.

        Raises:
            ValueError: If any input is invalid.
            TypeError: If any lag is not an int or inner knot fails.
        """
        if not isinstance(time_column, str) or not time_column:
            raise ValueError("LagFeatureGenerator: time_column must be a non-empty string")
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("LagFeatureGenerator: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError(
                    "LagFeatureGenerator: every column name must be a non-empty string"
                )
        lag_tuple = tuple(lags)
        if not lag_tuple:
            raise ValueError("LagFeatureGenerator: lags must be non-empty")
        for lag in lag_tuple:
            if not isinstance(lag, int):
                raise TypeError("LagFeatureGenerator: every lag must be an int")
            if lag < 1:
                raise ValueError("LagFeatureGenerator: every lag must be >= 1")
        with Tapestry() as inner:
            split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
            _LagAppendKnot(
                split=split_node,
                time_column=time_column,
                columns=column_tuple,
                lags=lag_tuple,
                _config=KnotConfig(id="append_lags"),
            )
        result = await self._run_inner(inner)
        lagged = result.outputs["append_lags"]
        if not isinstance(lagged, SplitManifest):
            raise TypeError("LagFeatureGenerator: inner knot did not return a SplitManifest")
        return lagged
