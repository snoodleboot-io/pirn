"""Unit tests for :class:`ConnectivityAnalyzer`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.connectivity_analyzer import (
    ConnectivityAnalyzer,
)
from pirn.domains.health.types.signal_frame import SignalFrame

_CFG = KnotConfig(id="c")
_SIGNAL = SignalFrame()
_KNOT = ConnectivityAnalyzer(signal=_SIGNAL, channel_names=[], method="plv", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            await _KNOT.process(signal="x", channel_names=[], method="plv")  # type: ignore[arg-type]

    async def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "channel_names"):
            await _KNOT.process(signal=_SIGNAL, channel_names=42, method="plv")  # type: ignore[arg-type]

    async def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            await _KNOT.process(signal=_SIGNAL, channel_names=[], method="bogus")

    async def test_returns_matrix(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, channel_names=["F3", "F4"], method="plv")
        assert isinstance(out, Mapping)
        assert "F3" in out
