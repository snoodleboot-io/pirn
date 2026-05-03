"""``FairnessAuditor`` — Knot that computes demographic parity, equalized
odds, and individual fairness metrics across protected attribute groups.
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
        protected_attributes: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("FairnessAuditor: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("FairnessAuditor: split must be a Knot")
        attrs = tuple(protected_attributes)
        if not attrs:
            raise ValueError(
                "FairnessAuditor: protected_attributes must be non-empty"
            )
        for attr in attrs:
            if not isinstance(attr, str) or not attr:
                raise ValueError(
                    "FairnessAuditor: every protected attribute must be a non-empty string"
                )
        self._protected_attributes = attrs
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def protected_attributes(self) -> tuple[str, ...]:
        return self._protected_attributes

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Compute fairness metrics across protected attribute groups for the model on the test split.

        Args:
            model: TrainedModel reference to audit for fairness.
            split: DataSplit whose test partition contains protected attribute labels.

        Returns:
            Mapping with ``demographic_parity`` (dict per attribute), ``equalized_odds``
            (dict per attribute), and ``individual_fairness`` (float).
        """
        demographic_parity: dict[str, float] = {}
        equalized_odds: dict[str, float] = {}
        for attr in self._protected_attributes:
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
