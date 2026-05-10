"""``TargetEncoder`` — replace a categorical column with the mean target
value per category.

The encoding is fit on the train partition and applied identically to
all partitions of the input :class:`SplitManifest`. The ``smoothing``
parameter blends per-category means with the global target mean to
guard against high-variance categories with few rows.

The orchestration layer composes :class:`Encoder` (with
``method="target"``) on the configured column. Concrete subclasses are
responsible for materialising the actual fit/transform; this knot's
output is a :class:`SplitManifest` whose feature lists are tagged
``encoded_target``.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``categorical_column``, ``target_column``,
       and ``smoothing`` via process().
    2. Validate all inputs.
    3. Wire Encoder (method="target") in an inner Tapestry.
    4. Run via _run_inner() and return the encoded SplitManifest.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.features.encoder import Encoder
from pirn.domains.ml.types.split_manifest import SplitManifest
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
        categorical_column: Knot | str,
        target_column: Knot | str,
        smoothing: Knot | float = 1.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            categorical_column=categorical_column,
            target_column=target_column,
            smoothing=smoothing,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        categorical_column: str = "",
        target_column: str = "",
        smoothing: float = 1.0,
        **_: Any,
    ) -> SplitManifest:
        """Apply target encoding to the categorical column across all split partitions and return the renamed SplitManifest.

        Args:
            split: SplitManifest whose partitions receive the target-encoded column.
            categorical_column: Non-empty name of the categorical column to encode.
            target_column: Non-empty name of the target column.
            smoothing: Smoothing factor; must be a number >= 0.

        Returns:
            SplitManifest with each partition renamed to include the ``encoded_target`` suffix.

        Raises:
            ValueError: If categorical_column or target_column are empty, or smoothing < 0.
            TypeError: If the inner encoder does not return a SplitManifest.
        """
        if not isinstance(categorical_column, str) or not categorical_column:
            raise ValueError("TargetEncoder: categorical_column must be a non-empty string")
        if not isinstance(target_column, str) or not target_column:
            raise ValueError("TargetEncoder: target_column must be a non-empty string")
        if not isinstance(smoothing, (int, float)):
            raise TypeError("TargetEncoder: smoothing must be a number")
        if float(smoothing) < 0.0:
            raise ValueError("TargetEncoder: smoothing must be >= 0.0")
        with Tapestry() as inner:
            split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
            Encoder(
                split=split_node,
                columns=(categorical_column,),
                method="target",
                _config=KnotConfig(id="encode"),
            )
        result = await self._run_inner(inner)
        encoded = result.outputs["encode"]
        if not isinstance(encoded, SplitManifest):
            raise TypeError("TargetEncoder: inner encoder did not return a SplitManifest")
        return encoded
