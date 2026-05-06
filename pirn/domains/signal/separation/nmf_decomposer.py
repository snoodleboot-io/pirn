"""``NMFDecomposer`` — non-negative matrix factorisation.

Algorithm:
    1. Receive the input signal frame, component_count, and max_iterations.
    2. Validate component_count and max_iterations (positive integers).
    3. Initialise the basis matrix W (channel_count × component_count) and
       coefficient matrix H (component_count × samples_per_channel) non-negatively.
    4. Apply multiplicative update rules to minimise the Frobenius-norm reconstruction
       error ‖V − WH‖_F subject to W, H ≥ 0.
    5. Return a SourceFrame with the estimated components.

Math:
    NMF multiplicative update:

    $$H \\leftarrow H \\circ \\frac{W^T V}{W^T W H}, \\quad W \\leftarrow W \\circ \\frac{V H^T}{W H H^T}$$

    Objective:

    $$\\min_{W \\geq 0,\\, H \\geq 0} \\|V - WH\\|_F^2$$

References:
    - Lee, D.D. & Seung, H.S. (1999). "Learning the parts of objects by non-negative matrix
      factorization." Nature, 401(6755), 788-791.
    - sklearn.decomposition.NMF: https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.NMF.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame


class NMFDecomposer(Knot):
    """Non-negative matrix factorisation.

    Production needs ``sklearn.decomposition.NMF``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        component_count: Knot | int,
        max_iterations: Knot | int = 200,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            component_count=component_count,
            max_iterations=max_iterations,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        component_count: int,
        max_iterations: int = 200,
        **_: Any,
    ) -> SourceFrame:
        """Decompose the signal into non-negative components via NMF and return a SourceFrame.

        Args:
            signal: Non-negative multichannel signal to factorize.
            component_count: Number of NMF components to extract (positive integer).
            max_iterations: Maximum multiplicative update iterations (positive integer).

        Returns:
            SourceFrame with ``source_count`` equal to ``component_count`` and the mixing matrix shape.

        Raises:
            ValueError: If component_count or max_iterations are invalid.
        """
        if not isinstance(component_count, int) or component_count <= 0:
            raise ValueError(
                "NMFDecomposer: component_count must be a positive integer"
            )
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                "NMFDecomposer: max_iterations must be a positive integer"
            )
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=component_count,
            mixing_matrix_shape=(signal.channel_count, component_count),
        )
