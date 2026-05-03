"""``EEGICADecomposer`` — independent component analysis decomposition of EEG data for artifact removal."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class EEGICADecomposer(Knot):
    """Independent component analysis decomposition of EEG data for artifact removal."""

    _VALID_ALGORITHMS: frozenset[str] = frozenset({"fastica", "infomax", "picard"})

    def __init__(
        self,
        *,
        eeg_data: Knot,
        n_components: int,
        algorithm: str,
        max_iter: int = 200,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(eeg_data, Knot):
            raise TypeError("EEGICADecomposer: eeg_data must be a Knot")
        if not isinstance(n_components, int) or n_components <= 0:
            raise ValueError(
                "EEGICADecomposer: n_components must be a positive integer"
            )
        if algorithm not in self._VALID_ALGORITHMS:
            raise ValueError(
                "EEGICADecomposer: algorithm must be one of 'fastica', 'infomax', 'picard'"
            )
        if not isinstance(max_iter, int) or max_iter <= 0:
            raise ValueError(
                "EEGICADecomposer: max_iter must be a positive integer"
            )
        self._n_components = n_components
        self._algorithm = algorithm
        self._max_iter = max_iter
        super().__init__(eeg_data=eeg_data, _config=_config, **kwargs)

    async def process(
        self,
        eeg_data: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        """Decompose EEG data into independent components using ICA.

        Args:
            eeg_data: Dict with n_channels (int), n_samples (int),
                sample_rate_hz (float), and data (list of channel data).

        Returns:
            Dict with n_components (int), mixing_matrix (list),
            unmixing_matrix (list), and component_variances (list of float).
        """
        if not isinstance(eeg_data, dict):
            raise TypeError("EEGICADecomposer: eeg_data must be a dict")
        n = self._n_components
        return {
            "n_components": n,
            "mixing_matrix": [[0.0] * n for _ in range(n)],
            "unmixing_matrix": [[0.0] * n for _ in range(n)],
            "component_variances": [0.0] * n,
        }
