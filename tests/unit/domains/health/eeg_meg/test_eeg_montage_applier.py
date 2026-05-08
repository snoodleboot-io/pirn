"""Unit tests for :class:`EEGMontageApplier`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.eeg_montage_applier import EEGMontageApplier
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload

_CFG = KnotConfig(id="ma")
_SIGNAL = SignalPayload(
    frame=SignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = EEGMontageApplier(signal=_SIGNAL, montage_name="standard_1020", reference="average", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalPayload"):
            await _KNOT.process(signal="not-a-signal", montage_name="standard_1020", reference="average")  # type: ignore[arg-type]

    async def test_rejects_empty_montage_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "montage_name"):
            await _KNOT.process(signal=_SIGNAL, montage_name="", reference="average")

    async def test_rejects_invalid_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "reference"):
            await _KNOT.process(signal=_SIGNAL, montage_name="standard_1020", reference="unknown")

    async def test_returns_dict_with_required_keys(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, montage_name="standard_1020", reference="average")
        assert isinstance(out, dict)
        assert "montage_name" in out
        assert "n_channels" in out
        assert "channel_positions" in out
        assert out["montage_name"] == "standard_1020"

    async def test_drop_channels_reduces_count(self) -> None:
        out_full = await _KNOT.process(signal=_SIGNAL, montage_name="standard_1020", reference="average")
        out_dropped = await _KNOT.process(signal=_SIGNAL, montage_name="standard_1020", reference="average", drop_channels=("Fp1",))
        assert out_dropped["n_channels"] == out_full["n_channels"] - 1
