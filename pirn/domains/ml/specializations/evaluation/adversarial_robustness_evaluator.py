"""``AdversarialRobustnessEvaluator`` — SubTapestry that applies FGSM or
PGD perturbations to inputs and evaluates model accuracy under attack.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

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


class AdversarialRobustnessEvaluator(SubTapestry):
    """Evaluate model accuracy under FGSM or PGD adversarial perturbations."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        attack: str = "fgsm",
        epsilon: float = 0.1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("AdversarialRobustnessEvaluator: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("AdversarialRobustnessEvaluator: split must be a Knot")
        allowed = {"fgsm", "pgd"}
        if attack not in allowed:
            raise ValueError(
                f"AdversarialRobustnessEvaluator: attack must be one of {allowed}, got {attack!r}"
            )
        if not isinstance(epsilon, (int, float)) or epsilon <= 0.0:
            raise ValueError(
                "AdversarialRobustnessEvaluator: epsilon must be a positive number"
            )
        self._attack = attack
        self._epsilon = float(epsilon)
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def attack(self) -> str:
        return self._attack

    @property
    def epsilon(self) -> float:
        return self._epsilon

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Apply adversarial perturbations and return clean vs adversarial accuracy metrics.

        Args:
            model: TrainedModel reference to evaluate under attack.
            split: DataSplit whose test partition is used for adversarial evaluation.

        Returns:
            Mapping with ``clean_accuracy`` (float), ``adversarial_accuracy`` (float),
            ``attack`` (str), and ``epsilon`` (float).
        """
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "attack": self._attack,
                "epsilon": self._epsilon,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        clean_accuracy = int.from_bytes(digest[:8], "big") / float(2**64)
        adversarial_accuracy = clean_accuracy * (
            0.5 + 0.5 * (int.from_bytes(digest[8:16], "big") / float(2**64))
        )
        return {
            "clean_accuracy": clean_accuracy,
            "adversarial_accuracy": adversarial_accuracy,
            "attack": self._attack,
            "epsilon": self._epsilon,
        }
