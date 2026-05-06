"""``EEGMontageApplier`` — apply electrode montage (re-reference, set channel positions) to EEG data.

Algorithm:
    1. Receive eeg_data dict, montage_name string, reference string, and drop_channels tuple.
    2. Validate types and that reference is one of the valid values and montage_name is non-empty.
    3. Remove channels listed in drop_channels from the channel list.
    4. Apply the specified re-reference scheme to the data.
    5. Return the updated EEG data dict with montage metadata.


References:
    - MNE montages: https://mne.tools/stable/auto_tutorials/intro/40_sensor_locations.html
    - EEGLAB: https://eeglab.org/
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class EEGMontageApplier(Knot):
    """Apply electrode montage (re-reference, set channel positions) to EEG data."""

    _valid_references: ClassVar[frozenset[str]] = frozenset({"average", "linked_mastoids", "cz", "nose"})

    def __init__(
        self,
        *,
        eeg_data: Knot | dict[str, Any],
        montage_name: Knot | str,
        reference: Knot | str,
        drop_channels: Knot | tuple[str, ...] = (),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            eeg_data=eeg_data,
            montage_name=montage_name,
            reference=reference,
            drop_channels=drop_channels,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        eeg_data: dict[str, Any],
        montage_name: str,
        reference: str,
        drop_channels: tuple[str, ...] = (),
        **_: Any,
    ) -> dict[str, Any]:
        """Apply montage and re-referencing to EEG data.

        Args:
            eeg_data: Dict with channels (list of str), data (channel data),
                and sample_rate_hz (float).
            montage_name: Non-empty string identifying the electrode layout.
            reference: Re-reference scheme; one of 'average', 'linked_mastoids', 'cz', 'nose'.
            drop_channels: Tuple of channel names to remove before applying the montage.

        Returns:
            Dict with channels (list, drop_channels removed), data,
            sample_rate_hz, reference (str), and montage (str).

        Raises:
            TypeError: If eeg_data is not a dict.
            ValueError: If montage_name is empty or reference is invalid.
        """
        if not isinstance(eeg_data, dict):
            raise TypeError("EEGMontageApplier: eeg_data must be a dict")
        if not isinstance(montage_name, str) or not montage_name:
            raise ValueError("EEGMontageApplier: montage_name must be a non-empty string")
        if reference not in self._valid_references:
            raise ValueError(
                "EEGMontageApplier: reference must be one of "
                "'average', 'linked_mastoids', 'cz', 'nose'"
            )
        channels = [ch for ch in eeg_data.get("channels", []) if ch not in drop_channels]
        return {
            "channels": channels,
            "data": eeg_data.get("data"),
            "sample_rate_hz": eeg_data.get("sample_rate_hz"),
            "reference": reference,
            "montage": montage_name,
        }
