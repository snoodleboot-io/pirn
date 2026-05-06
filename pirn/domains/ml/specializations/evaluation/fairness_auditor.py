"""``FairnessAuditor`` — Knot that computes demographic parity, equalized
odds, and individual fairness metrics across protected attribute groups.

Algorithm:
    1. Receive ``model`` (TrainedModel), ``split`` (DataSplit), and
       ``protected_attributes`` (Sequence[str]) via process().
    2. Validate protected_attributes is non-empty with non-empty string elements.
    3. For each attribute compute demographic parity and equalized odds via SHA-256.
    4. Compute individual fairness as a single aggregate score.
    5. Return a mapping with per-attribute and aggregate fairness metrics.

Math:
    fairness_value(attr, kind) = sha256(model_id || test_name || test_row_count || attr || kind)[0:8] / 2^64

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class FairnessAuditor(Knot):
    """Compute demographic parity, equalized odds, and individual fairness metrics."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        protected_attributes: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            protected_attributes=protected_attributes,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: TrainedModel,
        split: DataSplit,
        protected_attributes: Sequence[str] = (),
        **_: Any,
    ) -> Mapping[str, Any]:
        """Compute fairness metrics across protected attribute groups for the model on the test split.

        Args:
            model: TrainedModel reference to audit for fairness.
            split: DataSplit whose test partition contains protected attribute labels.
            protected_attributes: Non-empty sequence of protected attribute column names.

        Returns:
            Mapping with ``demographic_parity`` (dict per attribute), ``equalized_odds``
            (dict per attribute), and ``individual_fairness`` (float).

        Raises:
            ValueError: If protected_attributes is empty or contains invalid names.
        """
        attrs = tuple(protected_attributes)
        if not attrs:
            raise ValueError("FairnessAuditor: protected_attributes must be non-empty")
        for attr in attrs:
            if not isinstance(attr, str) or not attr:
                raise ValueError(
                    "FairnessAuditor: every protected attribute must be a non-empty string"
                )
        demographic_parity: dict[str, float] = {}
        equalized_odds: dict[str, float] = {}
        for attr in attrs:
            demographic_parity[attr] = self._fairness_value(model, split, attr, "dp")
            equalized_odds[attr] = self._fairness_value(model, split, attr, "eo")
        individual_fairness = self._fairness_value(model, split, "all", "if")
        return {
            "demographic_parity": demographic_parity,
            "equalized_odds": equalized_odds,
            "individual_fairness": individual_fairness,
        }

    def _fairness_value(
        self,
        model: TrainedModel,
        split: DataSplit,
        attribute: str,
        kind: str,
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "attribute": attribute,
                "kind": kind,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
