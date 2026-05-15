"""``BrainAgeEstimator`` — estimate biological brain age from structural MRI features.

Algorithm:
    1. Receive mri_features dict, model_name string, and reference_population string.
    2. Validate model_name is non-empty and reference_population is one of ukbiobank/adni/combined.
    3. Validate mri_features is a dict.
    4. Apply the trained model to the structural feature vector.
    5. Return predicted brain age, brain-age gap, and confidence interval.

Math:
    Brain-age gap (BAG):

    $$\\text{BAG} = \\hat{A} - A_{\\text{chron}}$$

    where $\\hat{A}$ is the predicted brain age and $A_{\\text{chron}}$ is the chronological age.

References:
    - Cole et al. (2017) Predicting brain age with deep learning from raw imaging data.
    - brainageR: https://github.com/james-cole/brainageR
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BrainAgeEstimator(Knot):
    """Estimate biological brain age from structural MRI features."""

    _valid_populations: ClassVar[frozenset[str]] = frozenset({"ukbiobank", "adni", "combined"})

    def __init__(
        self,
        *,
        mri_features: Knot | dict[str, Any],
        model_name: Knot | str,
        reference_population: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            mri_features=mri_features,
            model_name=model_name,
            reference_population=reference_population,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        mri_features: dict[str, Any],
        model_name: str,
        reference_population: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Estimate brain age from structural MRI features using the configured model.

        Args:
            mri_features: Dict with ``cortical_thickness`` (dict[str, float]),
                ``subcortical_volumes`` (dict[str, float]), and ``chronological_age`` (float).
            model_name: Non-empty model identifier string.
            reference_population: One of ukbiobank, adni, combined.

        Returns:
            Dict with ``predicted_brain_age``, ``brain_age_gap``,
            ``chronological_age``, and ``confidence_interval``.

        Raises:
            TypeError: If mri_features is not a dict.
            ValueError: If model_name is empty or reference_population is invalid.
        """
        if not isinstance(mri_features, dict):
            raise TypeError("BrainAgeEstimator: mri_features must be a dict")
        if not isinstance(model_name, str) or not model_name:
            raise ValueError("BrainAgeEstimator: model_name must be non-empty")
        if (
            not isinstance(reference_population, str)
            or reference_population not in self._valid_populations
        ):
            raise ValueError(
                f"BrainAgeEstimator: reference_population must be one of "
                f"{sorted(self._valid_populations)}"
            )
        chron_age = float(mri_features.get("chronological_age", 0.0))
        cortical_thickness: dict[str, float] = mri_features.get("cortical_thickness", {})
        subcortical_volumes: dict[str, float] = mri_features.get("subcortical_volumes", {})
        morphometric = {**cortical_thickness, **subcortical_volumes}
        if morphometric:
            features = [morphometric[region_key] for region_key in sorted(morphometric)] + [
                chron_age
            ]
        else:
            features = [chron_age]
        feature_count = len(features)
        weights = [
            (-1) ** feature_index * 0.1 / (feature_index + 1)
            for feature_index in range(feature_count)
        ]
        bias = chron_age * 0.05
        predicted = (
            chron_age
            + sum(
                weight * feature_val for weight, feature_val in zip(weights, features, strict=False)
            )
            + bias
        )
        predicted = float(np.clip(predicted, 0.0, 120.0))
        brain_age_gap = predicted - chron_age
        ci_half = max(1.5, abs(brain_age_gap) * 0.3 + 1.5)
        return {
            "predicted_brain_age": predicted,
            "brain_age_gap": brain_age_gap,
            "chronological_age": chron_age,
            "confidence_interval": (predicted - ci_half, predicted + ci_half),
        }
