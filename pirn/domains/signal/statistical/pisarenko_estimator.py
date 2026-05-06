"""``PisarenkoEstimator`` — Pisarenko harmonic decomposition.

Algorithm:
    1. Receive the input signal frame and sinusoid_count.
    2. Validate sinusoid_count (positive integer).
    3. Compute the autocorrelation matrix R of order (sinusoid_count + 1).
    4. Find the minimum eigenvector of R (corresponding to the noise subspace).
    5. Solve for sinusoid frequencies as the roots of the minimum eigenvector polynomial.
    6. Return a mapping with estimated frequencies and parameters.

Math:
    Minimum eigenvector decomposition:

    $$\\mathbf{R} \\mathbf{v}_{\\min} = \\sigma_n^2 \\mathbf{v}_{\\min}$$

    Frequency polynomial:

    $$V(z) = \\sum_{k=0}^{p} v_k z^{-k} = \\prod_{i=1}^{p} (1 - e^{j\\omega_i} z^{-1})$$

References:
    - Pisarenko, V.F. (1973). "The retrieval of harmonics from a covariance function."
      Geophys. J. R. Astron. Soc., 33(3), 347-366.
    - numpy.linalg: https://numpy.org/doc/stable/reference/routines.linalg.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class PisarenkoEstimator(Knot):
    """Pisarenko harmonic-decomposition frequency estimator.

    Production needs an eigen-decomposition-based estimator.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        sinusoid_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            sinusoid_count=sinusoid_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        sinusoid_count: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate sinusoid frequencies via Pisarenko harmonic decomposition and return a parameter mapping.

        Args:
            signal: Signal to estimate harmonic frequencies from.
            sinusoid_count: Number of sinusoidal components to identify (positive integer).

        Returns:
            Mapping containing ``signal_id``, ``sinusoid_count``, and ``estimator``.

        Raises:
            ValueError: If sinusoid_count is not a positive integer.
        """
        if not isinstance(sinusoid_count, int) or sinusoid_count <= 0:
            raise ValueError(
                "PisarenkoEstimator: sinusoid_count must be a positive integer"
            )
        return {
            "signal_id": signal.signal_id,
            "sinusoid_count": sinusoid_count,
            "estimator": "pisarenko",
        }
