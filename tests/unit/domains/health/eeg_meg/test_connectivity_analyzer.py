"""Unit tests for :class:`ConnectivityAnalyzer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.connectivity_analyzer import (
    ConnectivityAnalyzer,
)
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            ConnectivityAnalyzer(
                signal="x",  # type: ignore[arg-type]
                channel_names=[],
                method="plv",
                _config=KnotConfig(id="c"),
            )

    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "channel_names"):
            ConnectivityAnalyzer(
                signal=SignalFrame(),
                channel_names=42,  # type: ignore[arg-type]
                method="plv",
                _config=KnotConfig(id="c"),
            )

    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            ConnectivityAnalyzer(
                signal=SignalFrame(),
                channel_names=[],
                method="bogus",
                _config=KnotConfig(id="c"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_matrix(self) -> None:
        with Tapestry() as t:
            ConnectivityAnalyzer(
                signal=SignalFrame(),
                channel_names=["F3", "F4"],
                method="plv",
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert isinstance(out, Mapping)
        assert "F3" in out
