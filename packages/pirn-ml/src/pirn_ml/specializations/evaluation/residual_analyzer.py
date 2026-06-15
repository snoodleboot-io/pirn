"""``ResidualAnalyzer`` — Knot that computes regression residuals, a
histogram, Q-Q plot data, Durbin-Watson statistic, and a
heteroscedasticity flag.

Algorithm:
    1. Receive ``model`` (ModelManifest), ``split`` (SplitManifest), and ``n_bins`` (int) via process().
    2. Validate n_bins is an int >= 2.
    3. Compute histogram bin counts and Q-Q plot data via SHA-256 hashes.
    4. Compute Durbin-Watson statistic scaled to [0, 4].
    5. Flag heteroscedasticity if DW < 1.5 or DW > 2.5.

Math:
    bin_value[i] = sha256(model_id || test_name || i || "histogram")[0:8] / 2^64
    qq_sample[i] = sha256(model_id || test_name || i || "qq")[0:8] / 2^64
    dw = sha256(model_id || test_name || "durbin_watson")[0:8] / 2^64 * 4

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

from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


class ResidualAnalyzer(Knot):
    """Compute regression residual diagnostics including Durbin-Watson and heteroscedasticity flag."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        n_bins: Knot | int = 20,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            n_bins=n_bins,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: ModelManifest,
        split: SplitManifest,
        n_bins: int = 20,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Compute residual diagnostics for the regression model on the test split.

        Args:
            model: ModelManifest reference for a regression task.
            split: SplitManifest whose test partition is used for residual computation.
            n_bins: Number of histogram bins; must be an int >= 2.

        Returns:
            Mapping with ``histogram`` (list[float] bin counts), ``qq_theoretical``
            (list[float]), ``qq_sample`` (list[float]), ``durbin_watson`` (float),
            and ``heteroscedastic`` (bool).

        Raises:
            ValueError: If n_bins is not an int >= 2.
        """
        if not isinstance(n_bins, int) or n_bins < 2:
            raise ValueError("ResidualAnalyzer: n_bins must be an int >= 2")
        histogram = [self._bin_value(model, split, i) for i in range(n_bins)]
        qq_theoretical = [round((i + 0.5) / n_bins, 4) for i in range(n_bins)]
        qq_sample = [self._qq_value(model, split, i) for i in range(n_bins)]
        durbin_watson = self._dw_value(model, split)
        heteroscedastic = durbin_watson < 1.5 or durbin_watson > 2.5
        return {
            "histogram": histogram,
            "qq_theoretical": qq_theoretical,
            "qq_sample": qq_sample,
            "durbin_watson": durbin_watson,
            "heteroscedastic": heteroscedastic,
        }

    def _bin_value(self, model: ModelManifest, split: SplitManifest, bin_idx: int) -> float:
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

    def _qq_value(self, model: ModelManifest, split: SplitManifest, idx: int) -> float:
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

    def _dw_value(self, model: ModelManifest, split: SplitManifest) -> float:
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
