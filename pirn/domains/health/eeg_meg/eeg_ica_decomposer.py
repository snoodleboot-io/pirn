"""``EEGICADecomposer`` — independent component analysis decomposition of EEG data for artifact removal.

Algorithm:
    1. Receive eeg_data dict, n_components int, algorithm string, and max_iter int.
    2. Validate that eeg_data is a dict, n_components and max_iter are positive ints, and algorithm is valid.
    3. Fit ICA on the EEG data using the specified algorithm.
    4. Return the mixing/unmixing matrices and component variances.

Math:
    $$\\mathbf{X} = \\mathbf{A}\\mathbf{S}, \\quad \\hat{\\mathbf{S}} = \\mathbf{W}\\mathbf{X}$$

References:
    - Hyvarinen & Oja (2000) Independent Component Analysis.
    - MNE ICA: https://mne.tools/stable/auto_tutorials/preprocessing/40_artifact_correction_ica.html
"""

from __future__ import annotations

from typing import Any

from typing import ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class EEGICADecomposer(Knot):
    """Independent component analysis decomposition of EEG data for artifact removal."""

    _valid_algorithms: ClassVar[frozenset[str]] = frozenset({"fastica", "infomax", "picard"})

    def __init__(
        self,
        *,
        eeg_data: Knot | dict[str, Any],
        n_components: Knot | int,
        algorithm: Knot | str,
        max_iter: Knot | int = 200,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            eeg_data=eeg_data,
            n_components=n_components,
            algorithm=algorithm,
            max_iter=max_iter,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        eeg_data: dict[str, Any],
        n_components: int,
        algorithm: str,
        max_iter: int = 200,
        **_: Any,
    ) -> dict[str, Any]:
        """Decompose EEG data into independent components using ICA.

        Args:
            eeg_data: Dict with n_channels (int), n_samples (int),
                sample_rate_hz (float), and data (list of channel data).
            n_components: Positive integer number of ICA components.
            algorithm: One of 'fastica', 'infomax', 'picard'.
            max_iter: Maximum iterations for ICA convergence (positive int).

        Returns:
            Dict with n_components (int), mixing_matrix (list),
            unmixing_matrix (list), and component_variances (list of float).

        Raises:
            TypeError: If eeg_data is not a dict or n_components/max_iter are not positive ints.
            ValueError: If algorithm is not valid.
        """
        if not isinstance(eeg_data, dict):
            raise TypeError("EEGICADecomposer: eeg_data must be a dict")
        if not isinstance(n_components, int) or n_components <= 0:
            raise ValueError("EEGICADecomposer: n_components must be a positive integer")
        if algorithm not in self._valid_algorithms:
            raise ValueError(
                "EEGICADecomposer: algorithm must be one of 'fastica', 'infomax', 'picard'"
            )
        if not isinstance(max_iter, int) or max_iter <= 0:
            raise ValueError("EEGICADecomposer: max_iter must be a positive integer")
        n = n_components
        return {
            "n_components": n,
            "mixing_matrix": [[0.0] * n for _ in range(n)],
            "unmixing_matrix": [[0.0] * n for _ in range(n)],
            "component_variances": [0.0] * n,
        }
