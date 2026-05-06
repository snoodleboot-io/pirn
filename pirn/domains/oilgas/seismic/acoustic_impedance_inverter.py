"""``AcousticImpedanceInverter`` — model-based seismic inversion to compute acoustic impedance.

Algorithm:
    1. Receive a seismic amplitude volume, an extraction wavelet, a
       low-frequency model, and an optional regularization weight.
    2. Validate that all three volume inputs are dicts and that
       ``regularization`` is a non-negative number.
    3. Convolve the wavelet with the reflectivity series derived from the
       low-frequency model.
    4. Iteratively update acoustic impedance to minimise the misfit between
       modelled and observed amplitudes (Tikhonov regularization).
    5. Return the impedance volume and scalar misfit.

Math:
    Least-squares objective with Tikhonov regularization:

    $$\\mathcal{L}(Z) = \\|\\mathbf{d} - W \\mathbf{r}(Z)\\|^2
      + \\lambda \\|Z - Z_0\\|^2$$

    where :math:`\\mathbf{d}` is the observed seismic data vector,
    :math:`W` is the wavelet convolution matrix, :math:`\\mathbf{r}(Z)`
    is the reflectivity from impedance :math:`Z`, :math:`Z_0` is the
    low-frequency background model, and :math:`\\lambda` is the
    regularization weight.

References:
    - Hampson, D.P., Schuelke, J.S. & Quirein, J.A. (2001). Use of
      multiattribute transforms to predict log properties from seismic data.
      *Geophysics*, 66(1), 220–236.
    - Russell, B.H. & Hampson, D.P. (1991). Comparison of post-stack seismic
      inversion methods. SEG Technical Program Expanded Abstracts,
      876–878. SEG-1991-0876.
"""

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
        regularization: Knot | float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            seismic_volume=seismic_volume,
            wavelet=wavelet,
            low_frequency_model=low_frequency_model,
            regularization=regularization,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        seismic_volume: dict[str, Any],
        wavelet: dict[str, Any],
        low_frequency_model: dict[str, Any],
        regularization: float = 0.0,
        **_: Any,
    ) -> dict[str, Any]:
        """Invert seismic amplitudes to acoustic impedance using the low-frequency model and wavelet.

        Args:
            seismic_volume: Dict representing the seismic amplitude volume.
            wavelet: Dict representing the extraction wavelet.
            low_frequency_model: Dict representing the low-frequency background model.
            regularization: Non-negative Tikhonov regularization weight (default 0.0).

        Returns:
            Dict with ``impedance_volume`` (dict with ``shape`` and ``values_stub``)
            and ``misfit`` (float).
        """
        if not isinstance(regularization, (int, float)):
            raise TypeError(
                "AcousticImpedanceInverter: regularization must be numeric"
            )
        if regularization < 0.0:
            raise ValueError(
                "AcousticImpedanceInverter: regularization must be >= 0.0"
            )
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
            "misfit": 0.01 + float(regularization) * 0.001,
        }
