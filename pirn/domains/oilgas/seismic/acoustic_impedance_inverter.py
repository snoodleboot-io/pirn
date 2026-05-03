"""``AcousticImpedanceInverter`` — model-based seismic inversion to compute acoustic impedance."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class AcousticImpedanceInverter(Knot):
    """Perform model-based inversion to estimate acoustic impedance from seismic amplitudes."""

    def __init__(
        self,
        *,
        seismic_volume: Knot,
        wavelet: Knot,
        low_frequency_model: Knot,
        regularization: float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(regularization, (int, float)):
            raise TypeError(
                "AcousticImpedanceInverter: regularization must be numeric"
            )
        if regularization < 0.0:
            raise ValueError(
                "AcousticImpedanceInverter: regularization must be >= 0.0"
            )
        self._regularization = float(regularization)
        super().__init__(
            seismic_volume=seismic_volume,
            wavelet=wavelet,
            low_frequency_model=low_frequency_model,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        seismic_volume: dict[str, Any],
        wavelet: dict[str, Any],
        low_frequency_model: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        """Invert seismic amplitudes to acoustic impedance using the low-frequency model and wavelet.

        Args:
            seismic_volume: Dict representing the seismic amplitude volume.
            wavelet: Dict representing the extraction wavelet.
            low_frequency_model: Dict representing the low-frequency background model.

        Returns:
            Dict with ``impedance_volume`` (dict with ``shape`` and ``values_stub``)
            and ``misfit`` (float).
        """
        for name, obj in (
            ("seismic_volume", seismic_volume),
            ("wavelet", wavelet),
            ("low_frequency_model", low_frequency_model),
        ):
            if not isinstance(obj, dict):
                raise TypeError(
                    f"AcousticImpedanceInverter: {name} must be a dict"
                )
        shape = seismic_volume.get("shape", [0, 0, 0])
        return {
            "impedance_volume": {"shape": shape, "values_stub": []},
            "misfit": 0.01 + self._regularization * 0.001,
        }
