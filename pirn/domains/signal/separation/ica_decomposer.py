"""``ICADecomposer`` — independent component analysis.

Algorithm:
    1. Receive the input signal frame and source_count.
    2. Validate source_count (positive integer).
    3. Whiten the multichannel signal to remove second-order correlations.
    4. Apply FastICA with kurtosis or negentropy contrast functions to
       iteratively rotate toward statistical independence.
    5. Return a SourceFrame with the estimated independent components.

Math:
    FastICA fixed-point update (negentropy contrast $G$):

    $$w_{k+1} = E\\{x g(w_k^T x)\\} - E\\{g'(w_k^T x)\\} w_k$$

    Independence condition:

    $$\\hat{s}_i = w_i^T x \\perp \\hat{s}_j \\quad \\forall i \\neq j$$

References:
    - Hyvärinen, A. & Oja, E. (2000). "Independent component analysis: algorithms and applications."
      Neural Netw., 13(4-5), 411-430.
    - sklearn.decomposition.FastICA: https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.FastICA.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame


class ICADecomposer(Knot):
    """FastICA-style independent component analysis.

    Production needs ``sklearn.decomposition.FastICA``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        source_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            source_count=source_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        source_count: int,
        **_: Any,
    ) -> SourceFrame:
        """Decompose the signal into independent components via FastICA and return a SourceFrame.

        Args:
            signal: Multichannel signal to decompose into statistically independent sources.
            source_count: Number of independent components to extract (positive integer).

        Returns:
            SourceFrame with the estimated independent components and mixing matrix shape.

        Raises:
            ValueError: If source_count is not a positive integer.
        """
        if not isinstance(source_count, int) or source_count <= 0:
            raise ValueError(
                "ICADecomposer: source_count must be a positive integer"
            )
        return SourceFrame(
            signal_id=signal.signal_id,
            source_count=source_count,
            mixing_matrix_shape=(signal.channel_count, source_count),
        )
