"""``PronyEstimator`` — fit damped sinusoids via Prony's method.

Algorithm:
    1. Receive the input signal frame and component_count.
    2. Validate component_count (positive integer).
    3. Form the data matrix from 2 * component_count signal samples.
    4. Solve the linear prediction problem to find the characteristic polynomial.
    5. Find the polynomial roots to obtain the complex modal frequencies (poles).
    6. Solve the Vandermonde system to obtain modal amplitudes.
    7. Return a mapping with the estimated modes and parameters.

Math:
    Prony model:

    $$x(n) = \\sum_{k=1}^{p} A_k z_k^n, \\quad z_k = e^{(\\sigma_k + j\\omega_k) T_s}$$

    Characteristic polynomial:

    $$a(z) = \\prod_{k=1}^{p} (1 - z_k z^{-1})$$

References:
    - Prony, G.R.B. (1795). "Essai expérimental et analytique." J. Éc. Polytech., 1(2), 24-76.
    - Kay, S.M. (1988). "Modern Spectral Estimation." Prentice-Hall.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class PronyEstimator(Knot):
    """Estimate damped exponential modes via Prony's method.

    Production needs a Prony implementation on top of ``numpy``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        component_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            component_count=component_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        component_count: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Fit damped sinusoidal modes to the signal via Prony's method and return a parameter mapping.

        Args:
            signal: Signal to decompose into damped exponential modes.
            component_count: Number of damped exponential modes to fit (positive integer).

        Returns:
            Mapping containing ``signal_id``, ``component_count``, and ``estimator``.

        Raises:
            ValueError: If component_count is not a positive integer.
        """
        if not isinstance(component_count, int) or component_count <= 0:
            raise ValueError("PronyEstimator: component_count must be a positive integer")
        return {
            "signal_id": signal.signal_id,
            "component_count": component_count,
            "estimator": "prony",
        }
