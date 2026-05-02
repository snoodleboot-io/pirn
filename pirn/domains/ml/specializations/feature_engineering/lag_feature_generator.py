"""``LagFeatureGenerator`` — generate ``<column>_lag_<N>`` features for
time-series datasets.

For every requested ``(column, lag)`` pair the pipeline appends a new
feature name to each partition of the upstream :class:`DataSplit`. The
orchestration layer only updates the feature-name catalogue; concrete
subclasses are responsible for the row-level shifting that materialises
the lag values, ordered by the configured ``time_column``.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.specializations.feature_engineering._lag_append_knot import (
    _LagAppendKnot,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class LagFeatureGenerator(SubTapestry):
    """Append per-(column, lag) features to a time-series :class:`DataSplit`."""

    def __init__(
        self,
        *,
        split: Knot,
        time_column: str,
        columns: Sequence[str],
        lags: Sequence[int] = (1, 7),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("LagFeatureGenerator: split must be a Knot")
        if not isinstance(time_column, str) or not time_column:
            raise ValueError(
                "LagFeatureGenerator: time_column must be a non-empty string"
            )
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError(
                "LagFeatureGenerator: columns must be non-empty"
            )
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError(
                    "LagFeatureGenerator: every column name must be a "
                    "non-empty string"
                )
        lag_tuple = tuple(lags)
        if not lag_tuple:
            raise ValueError("LagFeatureGenerator: lags must be non-empty")
        for lag in lag_tuple:
            if not isinstance(lag, int):
                raise TypeError(
                    "LagFeatureGenerator: every lag must be an int"
                )
            if lag < 1:
                raise ValueError(
                    "LagFeatureGenerator: every lag must be >= 1"
                )
        self._time_column = time_column
        self._columns = column_tuple
        self._lags = lag_tuple
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            _LagAppendKnot(
                split=split_node,
                time_column=self._time_column,
                columns=self._columns,
                lags=self._lags,
                _config=KnotConfig(id="append_lags"),
            )
        result = await self._run_inner(inner)
        lagged = result.outputs["append_lags"]
        if not isinstance(lagged, DataSplit):
            raise TypeError(
                "LagFeatureGenerator: inner knot did not return a DataSplit"
            )
        return lagged
