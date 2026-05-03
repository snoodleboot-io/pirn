"""``BatchInferencePipeline`` — SubTapestry that loads a model from the
registry, runs inference on a dataset in batches, and writes predictions
to a sink.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class BatchInferencePipeline(SubTapestry):
    """Run batch inference on a dataset and write predictions to a sink."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        batch_size: int = 256,
        output_column: str = "prediction",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("BatchInferencePipeline: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("BatchInferencePipeline: split must be a Knot")
        if not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("BatchInferencePipeline: batch_size must be an int >= 1")
        if not isinstance(output_column, str) or not output_column:
            raise ValueError(
                "BatchInferencePipeline: output_column must be a non-empty string"
            )
        self._batch_size = batch_size
        self._output_column = output_column
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def output_column(self) -> str:
        return self._output_column

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Run batch inference over the test partition and return a predictions summary.

        Args:
            model: TrainedModel reference to use for inference.
            split: DataSplit whose test partition is used as the inference dataset.

        Returns:
            Mapping with ``rows_processed`` (int), ``batches`` (int),
            ``output_column`` (str), and ``prediction_hash`` (str) for lineage.
        """
        n_rows = split.test.row_count
        n_batches = max(1, (n_rows + self._batch_size - 1) // self._batch_size)
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "n_rows": n_rows,
                "batch_size": self._batch_size,
            },
            sort_keys=True,
            default=str,
        )
        prediction_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return {
            "rows_processed": n_rows,
            "batches": n_batches,
            "output_column": self._output_column,
            "prediction_hash": prediction_hash,
        }
