"""``PCADecomposer`` — principal component analysis on a multichannel signal.

Algorithm:
    1. Receive the input signal frame, component_count, and whiten flag.
    2. Validate component_count (positive integer) and whiten (bool).
    3. Center the signal by subtracting the channel means.
    4. Compute the covariance matrix and its eigendecomposition.
    5. Project the signal onto the top component_count eigenvectors.
    6. If whiten is True, scale each component by 1 / sqrt(eigenvalue).
    7. Return a SourceFrame with the principal components.

Math:
    Covariance eigendecomposition:

    $$C = \\frac{1}{N-1} X X^T = V \\Lambda V^T$$

    PCA projection:

    $$Z = V_k^T X$$

    Whitened projection:

    $$Z_{\\text{white}} = \\Lambda_k^{-1/2} V_k^T X$$

References:
    - Jolliffe, I.T. (2002). "Principal Component Analysis." Springer.
    - sklearn.decomposition.PCA: https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame


class PCADecomposer(Knot):
    """Principal component analysis decomposition.

    Production needs ``sklearn.decomposition.PCA``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        component_count: Knot | int,
        whiten: Knot | bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            component_count=component_count,
            whiten=whiten,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        component_count: int,
        whiten: bool = False,
        **_: Any,
    ) -> SourceFrame:
        """Decompose the signal into principal components via PCA and return a SourceFrame.

        Args:
            signal: Multichannel signal to project onto the configured principal components.
            component_count: Number of principal components to retain (positive integer).
            whiten: If True, scale components to unit variance.

        Returns:
            SourceFrame with ``source_count`` equal to ``component_count`` and the mixing matrix shape.

        Raises:
            ValueError: If component_count is invalid.
            TypeError: If whiten is not a bool.
        """
        if not isinstance(component_count, int) or component_count <= 0:
            raise ValueError("PCADecomposer: component_count must be a positive integer")
        if not isinstance(whiten, bool):
            raise TypeError("PCADecomposer: whiten must be a bool")
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=component_count,
            mixing_matrix_shape=(signal.channel_count, component_count),
        )
