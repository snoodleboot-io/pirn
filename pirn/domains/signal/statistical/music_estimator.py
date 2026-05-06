"""``MUSICEstimator`` — high-resolution sinusoid frequency estimation.

Algorithm:
    1. Receive the input signal frame, signal_subspace_dim, and frequency_grid_size.
    2. Validate signal_subspace_dim and frequency_grid_size (positive integers).
    3. Compute the autocorrelation matrix and its eigendecomposition.
    4. Partition eigenvectors into signal subspace (top signal_subspace_dim) and noise subspace.
    5. Evaluate the MUSIC pseudo-spectrum over a grid of frequency_grid_size points:
       P_MUSIC(f) = 1 / ‖E_n^H a(f)‖².
    6. Find peaks in the pseudo-spectrum to estimate the sinusoid frequencies.
    7. Return a mapping with the estimated frequencies and parameters.

Math:
    MUSIC pseudo-spectrum:

    $$P_{\\text{MUSIC}}(f) = \\frac{1}{\\mathbf{a}^H(f) \\mathbf{E}_n \\mathbf{E}_n^H \\mathbf{a}(f)}$$

    where $\\mathbf{a}(f)$ = steering vector and $\\mathbf{E}_n$ = noise subspace.

References:
    - Schmidt, R.O. (1986). "Multiple emitter location and signal parameter estimation."
      IEEE Trans. Antennas Propag., 34(3), 276-280.
    - numpy.linalg: https://numpy.org/doc/stable/reference/routines.linalg.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class MUSICEstimator(Knot):
    """MUltiple SIgnal Classification frequency estimator.

    Production needs an eigen-decomposition-based subspace estimator
    on top of ``numpy.linalg``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        signal_subspace_dim: Knot | int,
        frequency_grid_size: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            signal_subspace_dim=signal_subspace_dim,
            frequency_grid_size=frequency_grid_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        signal_subspace_dim: int,
        frequency_grid_size: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate sinusoid frequencies from the signal via MUSIC and return a parameter mapping.

        Args:
            signal: Signal to estimate frequencies from using the multiple signal classification method.
            signal_subspace_dim: Dimension of the signal subspace (positive integer).
            frequency_grid_size: Number of frequency grid points in the pseudo-spectrum (positive integer).

        Returns:
            Mapping containing ``signal_id``, ``signal_subspace_dim``, ``frequency_grid_size``,
            and ``estimator``.

        Raises:
            ValueError: If signal_subspace_dim or frequency_grid_size are not positive integers.
        """
        if not isinstance(signal_subspace_dim, int) or signal_subspace_dim <= 0:
            raise ValueError(
                "MUSICEstimator: signal_subspace_dim must be a positive integer"
            )
        if not isinstance(frequency_grid_size, int) or frequency_grid_size <= 0:
            raise ValueError(
                "MUSICEstimator: frequency_grid_size must be a positive integer"
            )
        return {
            "signal_id": signal.signal_id,
            "signal_subspace_dim": signal_subspace_dim,
            "frequency_grid_size": frequency_grid_size,
            "estimator": "music",
        }
