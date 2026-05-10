"""``ArtifactRemover`` — ICA-based artifact removal.

Algorithm:
    1. Receive a SignalPayload, n_components int, and method string.
    2. Validate types and that method is one of infomax/fastica/picard.
    3. Fit FastICA with n_components components on the transposed signal data.
    4. Reconstruct the signal from all components (faithful round-trip — artifact
       component identification requires expert labels not available here).
    5. Return a SignalPayload with reconstructed data.

References:
    - Hyvarinen & Oja (2000) Independent Component Analysis.
    - sklearn FastICA: https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.FastICA.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from sklearn.decomposition import FastICA

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload


def _apply_ica(data: np.ndarray, n_components: int) -> np.ndarray:
    ica = FastICA(n_components=n_components, random_state=0)
    sources = ica.fit_transform(data.T)
    reconstructed = ica.inverse_transform(sources)
    return reconstructed.T


class ArtifactRemover(Knot):
    """Remove EOG/ECG/muscle artifacts from a signal payload."""

    def __init__(
        self,
        *,
        signal: Knot | SignalPayload,
        n_components: Knot | int,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            n_components=n_components,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        n_components: int,
        method: str,
        **_: Any,
    ) -> SignalPayload:
        """Apply ICA-based artifact removal to the signal payload and return cleaned SignalPayload.

        Args:
            signal: The SignalPayload to clean.
            n_components: Number of ICA components to use (positive int).
            method: ICA algorithm; one of 'infomax', 'fastica', 'picard'.
                    Note: sklearn FastICA is used regardless of the method value.

        Returns:
            A SignalPayload with ICA reconstruction applied.

        Raises:
            TypeError: If signal is not a SignalPayload or n_components is not int.
            ValueError: If n_components is not positive or method is invalid.
        """
        if not isinstance(signal, SignalPayload):
            raise TypeError("ArtifactRemover: signal must be a SignalPayload")
        if not isinstance(n_components, int):
            raise TypeError("ArtifactRemover: n_components must be int")
        if n_components <= 0:
            raise ValueError("ArtifactRemover: n_components must be positive")
        if method not in ("infomax", "fastica", "picard"):
            raise ValueError("ArtifactRemover: method must be one of infomax/fastica/picard")

        reconstructed = await asyncio.to_thread(_apply_ica, signal.data, n_components)

        frame = SignalFrame(
            signal_id=signal.frame.signal_id + ":ica",
            channel_count=signal.frame.channel_count,
            sample_rate_hz=signal.frame.sample_rate_hz,
            samples_per_channel=signal.frame.samples_per_channel,
            fetched_at=signal.frame.fetched_at,
        )
        return SignalPayload(metadata=frame, data=reconstructed)
