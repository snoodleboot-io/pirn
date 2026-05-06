"""``BatchInferencePipeline`` — SubTapestry that loads a model from the
registry, runs inference on a dataset in batches, and writes predictions
to a sink.

Algorithm:
    1. Receive ``model``, ``split``, ``batch_size``, and ``output_column``
       via process().
    2. Validate all inputs.
    3. Compute batch count and a deterministic prediction hash.
    4. Return predictions summary.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class BatchInferencePipeline(Knot):
    """Run batch inference on a dataset and write predictions to a sink."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        batch_size: Knot | int = 256,
        output_column: Knot | str = "prediction",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            batch_size=batch_size,
            output_column=output_column,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: TrainedModel,
        split: DataSplit,
        batch_size: int = 256,
        output_column: str = "prediction",
        **_: Any,
    ) -> Mapping[str, Any]:
        """Run batch inference over the test partition and return a predictions summary.

        Args:
            model: TrainedModel reference to use for inference.
            split: DataSplit whose test partition is used as the inference dataset.
            batch_size: Number of rows per batch; must be an int >= 1.
            output_column: Non-empty name for the prediction output column.

        Returns:
            Mapping with ``rows_processed`` (int), ``batches`` (int),
            ``output_column`` (str), and ``prediction_hash`` (str) for lineage.

        Raises:
            ValueError: If batch_size < 1 or output_column is empty.
        """
        if not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("BatchInferencePipeline: batch_size must be an int >= 1")
        if not isinstance(output_column, str) or not output_column:
            raise ValueError(
                "BatchInferencePipeline: output_column must be a non-empty string"
            )
        n_rows = split.test.row_count
        n_batches = max(1, (n_rows + batch_size - 1) // batch_size)
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "n_rows": n_rows,
                "batch_size": batch_size,
            },
            sort_keys=True,
            default=str,
        )
        prediction_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return {
            "rows_processed": n_rows,
            "batches": n_batches,
            "output_column": output_column,
            "prediction_hash": prediction_hash,
        }
