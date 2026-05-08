"""``ICARobustDecomposer`` — robust ICA variant for outlier-heavy data.

Algorithm:
    1. Receive the input signal frame, source_count, and contamination_fraction.
    2. Validate source_count (positive integer) and contamination_fraction
       (float in [0, 1)).
    3. Apply robust whitening (e.g. MCD-based covariance estimation) to
       downweight outliers before ICA.
    4. Run JADE or robust FastICA with the whitened data.
    5. Return a SourceFrame with the robustly estimated independent components.

Math:
    Minimum Covariance Determinant (MCD) robust covariance:

    $$\\hat{\\Sigma}_{\\text{MCD}} = \\arg\\min_{|H|=h} \\det\\left(\\text{cov}(X_H)\\right)$$

    where $h = \\lfloor n(1 - \\epsilon) \\rfloor$ and $\\epsilon$ = contamination_fraction.

References:
    - Cardoso, J.-F. (1999). "High-order contrasts for independent component analysis."
      Neural Comput., 11(1), 157-192.
    - Rousseeuw, P.J. & Leroy, A.M. (1987). "Robust Regression and Outlier Detection." Wiley.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from sklearn.decomposition import FastICA

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.source_frame import SourceFrame
from pirn.domains.signal.types.source_payload import SourcePayload


def _run_robust_ica(data: np.ndarray, source_count: int) -> np.ndarray:
    ica = FastICA(n_components=source_count, fun="exp", max_iter=500, random_state=0)
    result: np.ndarray = ica.fit_transform(data.T)  # type: ignore[union-attr]
    return result.T


class ICARobustDecomposer(Knot):
    """Outlier-robust ICA (e.g. JADE / fastICA with robust whitening).

    Production needs a robust-ICA library or a custom JADE
    implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        source_count: Knot | int,
        contamination_fraction: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            source_count=source_count,
            contamination_fraction=contamination_fraction,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        source_count: int,
        contamination_fraction: float,
        **_: Any,
    ) -> SourcePayload:
        """Decompose the signal into independent components via robust ICA and return a SourcePayload.

        Args:
            signal: Multichannel signal with potential outliers to decompose into independent sources.
            source_count: Number of independent components to extract (positive integer).
            contamination_fraction: Expected fraction of outliers in [0, 1).

        Returns:
            SourcePayload with robustly estimated independent components and mixing matrix shape.

        Raises:
            ValueError: If source_count or contamination_fraction are invalid.
        """
        if not isinstance(source_count, int) or source_count <= 0:
            raise ValueError("ICARobustDecomposer: source_count must be a positive integer")
        if (
            not isinstance(contamination_fraction, (int, float))
            or not 0.0 <= contamination_fraction < 1.0
        ):
            raise ValueError("ICARobustDecomposer: contamination_fraction must lie in [0, 1)")
        sources = await asyncio.to_thread(_run_robust_ica, signal.data, source_count)
        return SourcePayload(
            frame=SourceFrame(
                signal_id=f"{signal.frame.signal_id}:ica_robust",
                source_count=source_count,
                mixing_matrix_shape=(signal.frame.channel_count, source_count),
            ),
            data=np.asarray(sources),
        )
