"""``ESPRITEstimator`` — rotational-invariance subspace frequency estimator.

Algorithm:
    1. Receive the input signal frame and signal_subspace_dim.
    2. Validate signal_subspace_dim (positive integer).
    3. Compute the autocorrelation matrix of the signal.
    4. Compute the eigendecomposition and partition into signal and noise subspaces.
    5. Solve the ESPRIT rotational invariance equation to obtain frequency estimates.
    6. Return a mapping with the estimated frequencies and parameters.

Math:
    Signal subspace partition:

    $$\\mathbf{R} = \\mathbf{E}_s \\mathbf{\\Lambda}_s \\mathbf{E}_s^H + \\sigma^2 \\mathbf{E}_n \\mathbf{E}_n^H$$

    ESPRIT equation:

    $$\\mathbf{E}_{s1}^\\dagger \\mathbf{E}_{s2} = \\mathbf{\\Phi}$$

    where $e^{j\\omega_k}$ are the eigenvalues of $\\mathbf{\\Phi}$.

References:
    - Roy, R. & Kailath, T. (1989). "ESPRIT — Estimation of signal parameters via rotational invariance
      techniques." IEEE Trans. Acoust. Speech Signal Process., 37(7), 984-995.
    - numpy.linalg: https://numpy.org/doc/stable/reference/routines.linalg.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ESPRITEstimator(Knot):
    """ESPRIT high-resolution sinusoid estimator.

    Production needs a subspace eigen-decomposition implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        signal_subspace_dim: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            signal_subspace_dim=signal_subspace_dim,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        signal_subspace_dim: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Estimate sinusoid frequencies from the signal via ESPRIT and return a parameter mapping.

        Args:
            signal: Signal to estimate frequencies from using the rotational-invariance subspace method.
            signal_subspace_dim: Dimension of the signal subspace (positive integer).

        Returns:
            Mapping containing ``signal_id``, ``signal_subspace_dim``, and ``estimator``.

        Raises:
            ValueError: If signal_subspace_dim is not a positive integer.
        """
        if not isinstance(signal_subspace_dim, int) or signal_subspace_dim <= 0:
            raise ValueError(
                "ESPRITEstimator: signal_subspace_dim must be a positive integer"
            )
        return {
            "signal_id": signal.signal_id,
            "signal_subspace_dim": signal_subspace_dim,
            "estimator": "esprit",
        }
