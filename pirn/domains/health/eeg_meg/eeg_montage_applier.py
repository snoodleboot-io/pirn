"""``EEGMontageApplier`` — apply electrode montage (re-reference, set channel positions) to EEG data."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class EEGMontageApplier(Knot):
    """Apply electrode montage (re-reference, set channel positions) to EEG data."""

    _VALID_REFERENCES: frozenset[str] = frozenset(
        {"average", "linked_mastoids", "cz", "nose"}
    )

    def __init__(
        self,
        *,
        eeg_data: Knot,
        montage_name: str,
        reference: str,
        drop_channels: tuple[str, ...] = (),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(eeg_data, Knot):
            raise TypeError("EEGMontageApplier: eeg_data must be a Knot")
        if not isinstance(montage_name, str) or not montage_name:
            raise ValueError(
                "EEGMontageApplier: montage_name must be a non-empty string"
            )
        if reference not in self._VALID_REFERENCES:
            raise ValueError(
                "EEGMontageApplier: reference must be one of "
                "'average', 'linked_mastoids', 'cz', 'nose'"
            )
        self._montage_name = montage_name
        self._reference = reference
        self._drop_channels = drop_channels
        super().__init__(eeg_data=eeg_data, _config=_config, **kwargs)

    async def process(
        self,
        eeg_data: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        """Apply montage and re-referencing to EEG data.

        Args:
            eeg_data: Dict with channels (list of str), data (channel data),
                and sample_rate_hz (float).

        Returns:
            Dict with channels (list, drop_channels removed), data,
            sample_rate_hz, reference (str), and montage (str).
        """
        if not isinstance(eeg_data, dict):
            raise TypeError("EEGMontageApplier: eeg_data must be a dict")
        channels = [
            ch for ch in eeg_data.get("channels", [])
            if ch not in self._drop_channels
        ]
        return {
            "channels": channels,
            "data": eeg_data.get("data"),
            "sample_rate_hz": eeg_data.get("sample_rate_hz"),
            "reference": self._reference,
            "montage": self._montage_name,
        }
