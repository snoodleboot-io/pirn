"""Unit tests for :class:`SourceLocalizer`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.source_localizer import SourceLocalizer
from pirn.domains.health.types.health_signal_frame import HealthSignalFrame
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="s")
_SIGNAL = HealthSignalPayload(
    metadata=HealthSignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = SourceLocalizer(signal=_SIGNAL, method="mne", source_labels=[], _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "HealthSignalPayload"):
            await _KNOT.process(signal="x", method="mne", source_labels=[])  # type: ignore[arg-type]

    async def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            await _KNOT.process(signal=_SIGNAL, method="bogus", source_labels=[])

    async def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "source_labels"):
            await _KNOT.process(signal=_SIGNAL, method="mne", source_labels=42)  # type: ignore[arg-type]

    async def test_rejects_non_string_label(self) -> None:
        with self.assertRaisesRegex(TypeError, "string"):
            await _KNOT.process(signal=_SIGNAL, method="mne", source_labels=[1])  # type: ignore[list-item]

    async def test_returns_source_mapping(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, method="dspm", source_labels=["lh.frontal"])
        assert isinstance(out, Mapping)
        assert "lh.frontal" in out
