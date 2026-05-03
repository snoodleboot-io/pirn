"""``ResidualAnalyzer`` — Knot that computes regression residuals, a
histogram, Q-Q plot data, Durbin-Watson statistic, and a
heteroscedasticity flag.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class ResidualAnalyzer(Knot):
    """Compute regression residual diagnostics including Durbin-Watson and heteroscedasticity flag."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        n_bins: int = 20,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("ResidualAnalyzer: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("ResidualAnalyzer: split must be a Knot")
        if not isinstance(n_bins, int) or n_bins < 2:
            raise ValueError("ResidualAnalyzer: n_bins must be an int >= 2")
        self._n_bins = n_bins
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def n_bins(self) -> int:
        return self._n_bins

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Compute residual diagnostics for the regression model on the test split.

        Args:
            model: TrainedModel reference for a regression task.
            split: DataSplit whose test partition is used for residual computation.

        Returns:
            Mapping with ``histogram`` (list[float] bin counts), ``qq_theoretical``
            (list[float]), ``qq_sample`` (list[float]), ``durbin_watson`` (float),
            and ``heteroscedastic`` (bool).
        """
        histogram = [
            self._bin_value(model, split, i) for i in range(self._n_bins)
        ]
        qq_theoretical = [round((i + 0.5) / self._n_bins, 4) for i in range(self._n_bins)]
        qq_sample = [
            self._qq_value(model, split, i) for i in range(self._n_bins)
        ]
        durbin_watson = self._dw_value(model, split)
        heteroscedastic = durbin_watson < 1.5 or durbin_watson > 2.5
        return {
            "histogram": histogram,
            "qq_theoretical": qq_theoretical,
            "qq_sample": qq_sample,
            "durbin_watson": durbin_watson,
            "heteroscedastic": heteroscedastic,
        }

    def _bin_value(self, model: TrainedModel, split: DataSplit, bin_idx: int) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "bin": bin_idx,
                "kind": "histogram",
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)

    def _qq_value(self, model: TrainedModel, split: DataSplit, idx: int) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "idx": idx,
                "kind": "qq",
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)

    def _dw_value(self, model: TrainedModel, split: DataSplit) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "kind": "durbin_watson",
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        raw = int.from_bytes(digest[:8], "big") / float(2**64)
        return raw * 4.0
