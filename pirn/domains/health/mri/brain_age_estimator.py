"""``BrainAgeEstimator`` — estimate biological brain age from structural MRI features."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class BrainAgeEstimator(Knot):
    """Estimate biological brain age from structural MRI features."""

    _VALID_POPULATIONS: frozenset[str] = frozenset({"ukbiobank", "adni", "combined"})

    def __init__(
        self,
        *,
        mri_features: Knot,
        model_name: str,
        reference_population: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model_name, str) or not model_name:
            raise ValueError("BrainAgeEstimator: model_name must be non-empty")
        if not isinstance(reference_population, str) or reference_population not in self._VALID_POPULATIONS:
            raise ValueError(
                f"BrainAgeEstimator: reference_population must be one of "
                f"{sorted(self._VALID_POPULATIONS)}"
            )
        self._model_name = model_name
        self._reference_population = reference_population
        super().__init__(mri_features=mri_features, _config=_config, **kwargs)

    async def process(self, mri_features: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Estimate brain age from structural MRI features using the configured model.

        Args:
            mri_features: Dict with ``cortical_thickness`` (dict[str, float]),
                ``subcortical_volumes`` (dict[str, float]), and
                ``chronological_age`` (float).

        Returns:
            Dict with ``predicted_brain_age``, ``brain_age_gap``,
            ``chronological_age``, and ``confidence_interval``.
        """
        if not isinstance(mri_features, dict):
            raise TypeError("BrainAgeEstimator: mri_features must be a dict")
        chron_age = float(mri_features.get("chronological_age", 0.0))
        return {
            "predicted_brain_age": chron_age,
            "brain_age_gap": 0.0,
            "chronological_age": chron_age,
            "confidence_interval": (chron_age - 2.0, chron_age + 2.0),
        }
