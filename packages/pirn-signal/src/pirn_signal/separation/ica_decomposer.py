"""``ICADecomposer`` — independent component analysis.

Algorithm:
    1. Receive the input signal payload and source_count.
    2. Validate source_count (positive integer).
    3. Whiten the multichannel signal to remove second-order correlations.
    4. Apply FastICA with kurtosis or negentropy contrast functions to
       iteratively rotate toward statistical independence.
    5. Return a SourcePayload with the estimated independent components.

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

import asyncio
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from sklearn.decomposition import FastICA

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.source_frame import SourceFrame
from pirn_signal.types.source_payload import SourcePayload


def _run_ica(data: np.ndarray, source_count: int) -> np.ndarray:
    ica = FastICA(n_components=source_count, random_state=0, max_iter=500)
    sources: np.ndarray = ica.fit_transform(data.T).T  # type: ignore[union-attr]  # shape: (source_count, samples)
    return sources


class ICADecomposer(Knot):
    """FastICA-style independent component analysis."""

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
        signal: SignalPayload,
        source_count: int,
        **_: Any,
    ) -> SourcePayload:
        """Decompose the signal into independent components via FastICA.

        Args:
            signal: Multichannel signal payload to decompose into statistically independent sources.
            source_count: Number of independent components to extract (positive integer).

        Returns:
            SourcePayload with the estimated independent components and mixing matrix shape.

        Raises:
            ValueError: If source_count is not a positive integer.
        """
        if not isinstance(source_count, int) or source_count <= 0:
            raise ValueError("ICADecomposer: source_count must be a positive integer")
        sources = await asyncio.to_thread(_run_ica, signal.data, source_count)
        return SourcePayload(
            metadata=SourceFrame(
                signal_id=f"{signal.frame.signal_id}:ica",
                source_count=source_count,
                mixing_matrix_shape=(signal.frame.channel_count, source_count),
            ),
            data=sources,
        )
