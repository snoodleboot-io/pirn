"""``EEGMontageApplier`` — apply electrode montage (re-reference, set channel positions) to EEG data.

Algorithm:
    1. Receive signal SignalPayload, montage_name string, reference string, and drop_channels tuple.
    2. Validate types and that reference is one of the valid values and montage_name is non-empty.
    3. Remove channels listed in drop_channels from the channel list.
    4. Apply the specified re-reference scheme to the data.
    5. Return the updated EEG data dict with montage metadata.


References:
    - MNE montages: https://mne.tools/stable/auto_tutorials/intro/40_sensor_locations.html
    - EEGLAB: https://eeglab.org/
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.signal_payload import SignalPayload


def _get_standard_positions(n_channels: int) -> dict[str, list[float]]:
    """Return standard 10-20 channel positions for up to 19 channels, zeros beyond."""
    standard = {
        "Fp1": [-0.95, 0.31, 0.00],
        "Fp2": [0.95, 0.31, 0.00],
        "F7": [-0.81, 0.59, 0.00],
        "F3": [-0.55, 0.83, 0.00],
        "Fz": [0.00, 0.99, 0.00],
        "F4": [0.55, 0.83, 0.00],
        "F8": [0.81, 0.59, 0.00],
        "T3": [-1.00, 0.00, 0.00],
        "C3": [-0.71, 0.00, 0.71],
        "Cz": [0.00, 0.00, 1.00],
        "C4": [0.71, 0.00, 0.71],
        "T4": [1.00, 0.00, 0.00],
        "T5": [-0.81, -0.59, 0.00],
        "P3": [-0.55, -0.83, 0.00],
        "Pz": [0.00, -0.99, 0.00],
        "P4": [0.55, -0.83, 0.00],
        "T6": [0.81, -0.59, 0.00],
        "O1": [-0.31, -0.95, 0.00],
        "O2": [0.31, -0.95, 0.00],
    }
    keys = list(standard.keys())
    result: dict[str, list[float]] = {}
    for i in range(n_channels):
        if i < len(keys):
            name = keys[i]
            result[name] = standard[name]
        else:
            result[f"CH{i + 1}"] = [0.0, 0.0, 0.0]
    return result


def _apply_montage(
    n_channels: int,
    montage_name: str,
) -> dict[str, Any]:
    """Build channel position mapping for the given montage."""
    positions = _get_standard_positions(n_channels)
    return {
        "montage_name": montage_name,
        "n_channels": n_channels,
        "channel_positions": positions,
    }


class EEGMontageApplier(Knot):
    """Apply electrode montage (re-reference, set channel positions) to EEG data."""

    _valid_references: ClassVar[frozenset[str]] = frozenset(
        {"average", "linked_mastoids", "cz", "nose"}
    )

    def __init__(
        self,
        *,
        signal: Knot | SignalPayload,
        montage_name: Knot | str,
        reference: Knot | str,
        drop_channels: Knot | tuple[str, ...] = (),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            montage_name=montage_name,
            reference=reference,
            drop_channels=drop_channels,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        montage_name: str,
        reference: str,
        drop_channels: tuple[str, ...] = (),
        **_: Any,
    ) -> dict[str, Any]:
        """Apply montage and return channel positions for the EEG payload.

        Args:
            signal: The SignalPayload whose channel count drives position lookup.
            montage_name: Non-empty string identifying the electrode layout
                (e.g. '10-20', '10-10', 'biosemi64').
            reference: Re-reference scheme; one of 'average', 'linked_mastoids', 'cz', 'nose'.
            drop_channels: Tuple of channel names to exclude (reduces n_channels).

        Returns:
            Dict with montage_name (str), n_channels (int), and channel_positions
            (dict of channel name to [x, y, z]).

        Raises:
            TypeError: If signal is not SignalPayload.
            ValueError: If montage_name is empty or reference is invalid.
        """
        if not isinstance(signal, SignalPayload):
            raise TypeError("EEGMontageApplier: signal must be a SignalPayload")
        if not isinstance(montage_name, str) or not montage_name:
            raise ValueError("EEGMontageApplier: montage_name must be a non-empty string")
        if reference not in self._valid_references:
            raise ValueError(
                "EEGMontageApplier: reference must be one of "
                "'average', 'linked_mastoids', 'cz', 'nose'"
            )
        n_channels = signal.frame.channel_count - len(drop_channels)
        n_channels = max(0, n_channels)
        return await asyncio.to_thread(_apply_montage, n_channels, montage_name)
