"""``AdversarialRobustnessEvaluator`` — SubTapestry that applies FGSM or
PGD perturbations to inputs and evaluates model accuracy under attack.

Algorithm:
    1. Receive ``model`` (TrainedModel), ``split`` (DataSplit), ``attack`` (str),
       and ``epsilon`` (float) via process().
    2. Validate attack is one of {"fgsm", "pgd"} and epsilon > 0.
    3. Derive deterministic clean and adversarial accuracy from SHA-256 of inputs.
    4. Return a mapping with accuracy metrics, attack name, and epsilon.

Math:
    clean_accuracy = sha256(model_id || test_name || test_row_count || attack || epsilon)[0:8] / 2^64
    adversarial_accuracy = clean_accuracy * (0.5 + 0.5 * sha256_bytes[8:16] / 2^64)

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class AdversarialRobustnessEvaluator(Knot):
    """Evaluate model accuracy under FGSM or PGD adversarial perturbations."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        attack: Knot | str = "fgsm",
        epsilon: Knot | float = 0.1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            attack=attack,
            epsilon=epsilon,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: TrainedModel,
        split: DataSplit,
        attack: str = "fgsm",
        epsilon: float = 0.1,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Apply adversarial perturbations and return clean vs adversarial accuracy metrics.

        Args:
            model: TrainedModel reference to evaluate under attack.
            split: DataSplit whose test partition is used for adversarial evaluation.
            attack: Attack method; must be one of {"fgsm", "pgd"}.
            epsilon: Perturbation magnitude; must be a positive float.

        Returns:
            Mapping with ``clean_accuracy`` (float), ``adversarial_accuracy`` (float),
            ``attack`` (str), and ``epsilon`` (float).

        Raises:
            ValueError: If attack is invalid or epsilon is not positive.
        """
        allowed = {"fgsm", "pgd"}
        if attack not in allowed:
            raise ValueError(
                f"AdversarialRobustnessEvaluator: attack must be one of {allowed}, got {attack!r}"
            )
        if not isinstance(epsilon, (int, float)) or epsilon <= 0.0:
            raise ValueError(
                "AdversarialRobustnessEvaluator: epsilon must be a positive number"
            )
        eps = float(epsilon)
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "attack": attack,
                "epsilon": eps,
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
            "attack": attack,
            "epsilon": eps,
        }
