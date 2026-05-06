"""``ArtifactRemover`` — ICA-based artifact removal.

Production version uses ``mne.preprocessing.ICA`` or AutoReject.
This stub validates inputs and returns the signal unchanged.

Algorithm:
    1. Receive a SignalFrame, n_components int, and method string.
    2. Validate types and that method is one of infomax/fastica/picard.
    3. Fit ICA with n_components components using the specified method.
    4. Identify and remove artifact components (EOG/ECG/muscle).
    5. Return the cleaned SignalFrame.


References:
    - Hyvarinen & Oja (2000) Independent Component Analysis.
    - MNE ICA: https://mne.tools/stable/auto_tutorials/preprocessing/40_artifact_correction_ica.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_frame import SignalFrame


class ArtifactRemover(Knot):
    """Remove EOG/ECG/muscle artifacts from a signal frame."""

    def __init__(
        self,
        *,
        signal: Knot | SignalFrame,
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
        signal: SignalFrame,
        n_components: int,
        method: str,
        **_: Any,
    ) -> SignalFrame:
        """Apply ICA-based artifact removal to the signal frame and return the cleaned SignalFrame.

        Args:
            signal: The SignalFrame to clean.
            n_components: Number of ICA components to use (positive int).
            method: ICA algorithm; one of 'infomax', 'fastica', 'picard'.

        Returns:
            A SignalFrame with artifacts removed.

        Raises:
            TypeError: If signal is not a SignalFrame or n_components is not int.
            ValueError: If n_components is not positive or method is invalid.
        """
        if not isinstance(signal, SignalFrame):
            raise TypeError("ArtifactRemover: signal must be a SignalFrame")
        if not isinstance(n_components, int):
            raise TypeError("ArtifactRemover: n_components must be int")
        if n_components <= 0:
            raise ValueError("ArtifactRemover: n_components must be positive")
        if method not in ("infomax", "fastica", "picard"):
            raise ValueError("ArtifactRemover: method must be one of infomax/fastica/picard")
        return signal
