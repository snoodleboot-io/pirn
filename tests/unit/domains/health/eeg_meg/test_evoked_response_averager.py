"""Unit tests for :class:`EvokedResponseAverager`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.evoked_response_averager import (
    EvokedResponseAverager,
)
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "epochs"):
            EvokedResponseAverager(
                epochs=42,  # type: ignore[arg-type]
                condition="target",
                _config=KnotConfig(id="e"),
            )

    def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            EvokedResponseAverager(
                epochs=[],
                condition="target",
                _config=KnotConfig(id="e"),
            )

    def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            EvokedResponseAverager(
                epochs=["x"],  # type: ignore[list-item]
                condition="target",
                _config=KnotConfig(id="e"),
            )

    def test_rejects_empty_condition(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            EvokedResponseAverager(
                epochs=[SignalFrame()],
                condition="",
                _config=KnotConfig(id="e"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_signal_frame(self) -> None:
        with Tapestry() as t:
            EvokedResponseAverager(
                epochs=[SignalFrame(signal_id="ep0")],
                condition="target",
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert isinstance(out, SignalFrame)
        assert "target" in out.signal_id
