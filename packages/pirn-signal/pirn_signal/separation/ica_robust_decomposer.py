"""``ICARobustDecomposer`` — robust ICA variant for outlier-heavy data.

Algorithm:
    1. Receive the input signal frame, source_count, and contamination_fraction.
    2. Validate source_count (positive integer) and contamination_fraction
       (float in [0, 1)).
    3. Trim the contaminated fraction: rank the time samples by Mahalanobis distance
       from the sample mean and set aside the most outlying
       ``contamination_fraction`` of them, the trimmed-covariance idea MCD
       formalises.
    4. Estimate the FastICA unmixing on the retained samples only, then apply it to
       every sample, so the outliers are unmixed by a model they did not distort.
    5. Return a SourcePayload with the robustly estimated independent components.

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
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.bindings.sklearn_decomposition_binding import SklearnDecompositionBinding
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.source_frame import SourceFrame
from pirn_signal.types.source_payload import SourcePayload


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
            contamination_fraction: Fraction of the most outlying time samples in
                [0, 1) to exclude when estimating the unmixing matrix. ``0.0`` fits on
                every sample, i.e. plain FastICA.

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
        sources = await asyncio.to_thread(
            ICARobustDecomposer._run_robust_ica,
            signal.data,
            source_count,
            float(contamination_fraction),
        )
        return SourcePayload(
            metadata=SourceFrame(
                signal_id=f"{signal.metadata.signal_id}:ica_robust",
                source_count=source_count,
                mixing_matrix_shape=(signal.metadata.channel_count, source_count),
            ),
            data=sources,
        )

    @staticmethod
    def _run_robust_ica(
        data: NDArray[np.floating[Any]], source_count: int, contamination_fraction: float
    ) -> NDArray[np.float64]:
        """Fit FastICA on the clean core of the data and unmix everything with it.

        Args:
            data: Observations shaped ``(channels, samples)``.
            source_count: Number of independent components.
            contamination_fraction: Fraction of the most outlying samples to exclude
                from the fit.

        Returns:
            Source estimates shaped ``(source_count, samples)``.
        """
        decomposition = SklearnDecompositionBinding.load()
        observations = np.atleast_2d(data).T
        retained = ICARobustDecomposer._clean_core(observations, contamination_fraction)
        result = decomposition.fast_ica_fit_subset(
            observations[retained],
            observations,
            source_count,
            max_iterations=500,
            contrast="exp",
        )
        return result.T

    @staticmethod
    def _clean_core(
        observations: NDArray[np.floating[Any]], contamination_fraction: float
    ) -> NDArray[np.int_]:
        """Indices of the samples to keep, dropping the most outlying fraction.

        Outlyingness is the Mahalanobis distance from the sample mean under the sample
        covariance (pseudo-inverted, so a rank-deficient channel set is tolerated) —
        the ranking a trimmed-covariance estimator minimises over.

        Args:
            observations: Samples shaped ``(samples, channels)``.
            contamination_fraction: Fraction in [0, 1) to drop.

        Returns:
            Sorted indices of the retained samples; every sample when the fraction is
            zero or the trim would leave too few samples to fit.
        """
        sample_count = observations.shape[0]
        drop_count = int(np.floor(contamination_fraction * sample_count))
        minimum_kept = max(observations.shape[1] + 1, 2)
        if drop_count <= 0 or sample_count - drop_count < minimum_kept:
            everything: NDArray[np.int_] = np.arange(sample_count, dtype=np.int_)
            return everything
        centred = observations - observations.mean(axis=0)
        precision = np.linalg.pinv(
            np.cov(centred, rowvar=False, ddof=1).reshape(
                observations.shape[1], observations.shape[1]
            )
        )
        distances: NDArray[np.float64] = np.asarray(
            np.einsum("ij,jk,ik->i", centred, precision, centred), dtype=np.float64
        )
        retained: NDArray[np.int_] = np.sort(
            np.argsort(distances)[: sample_count - drop_count]
        ).astype(np.int_)
        return retained
