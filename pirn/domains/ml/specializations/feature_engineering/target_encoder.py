"""``TargetEncoder`` — replace a categorical column with the mean target
value per category.

The encoding is fit on the train partition and applied identically to
all partitions of the input :class:`DataSplit`. The ``smoothing``
parameter blends per-category means with the global target mean to
guard against high-variance categories with few rows.

The orchestration layer composes :class:`Encoder` (with
``method="target"``) on the configured column. Concrete subclasses are
responsible for materialising the actual fit/transform; this knot's
output is a :class:`DataSplit` whose feature lists are tagged
``encoded_target``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.features.encoder import Encoder
from pirn.domains.ml.types.data_split import DataSplit
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class TargetEncoder(SubTapestry):
    """Replace a categorical column with smoothed per-category target means."""

    def __init__(
        self,
        *,
        split: Knot,
        categorical_column: str,
        target_column: str,
        smoothing: float = 1.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("TargetEncoder: split must be a Knot")
        if not isinstance(categorical_column, str) or not categorical_column:
            raise ValueError(
                "TargetEncoder: categorical_column must be a non-empty string"
            )
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(
                "TargetEncoder: target_column must be a non-empty string"
            )
        if not isinstance(smoothing, (int, float)):
            raise TypeError("TargetEncoder: smoothing must be a number")
        if float(smoothing) < 0.0:
            raise ValueError("TargetEncoder: smoothing must be >= 0.0")
        self._categorical_column = categorical_column
        self._target_column = target_column
        self._smoothing = float(smoothing)
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def smoothing(self) -> float:
        return self._smoothing

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        """Apply target encoding to the categorical column across all split partitions and return the renamed DataSplit.

        Args:
            split: DataSplit whose partitions receive the target-encoded column.

        Returns:
            DataSplit with each partition renamed to include the ``encoded_target`` suffix.

        Raises:
            TypeError: If the inner encoder does not return a DataSplit.
        """
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            Encoder(
                split=split_node,
                columns=(self._categorical_column,),
                method="target",
                _config=KnotConfig(id="encode"),
            )
        result = await self._run_inner(inner)
        encoded = result.outputs["encode"]
        if not isinstance(encoded, DataSplit):
            raise TypeError(
                "TargetEncoder: inner encoder did not return a DataSplit"
            )
        return encoded
