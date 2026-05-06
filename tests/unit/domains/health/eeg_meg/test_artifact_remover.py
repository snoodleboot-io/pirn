"""Unit tests for :class:`ArtifactRemover`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.artifact_remover import ArtifactRemover
from pirn.domains.health.types.signal_frame import SignalFrame


_CFG = KnotConfig(id="r")
_SIGNAL = SignalFrame(signal_id="s")
_KNOT = ArtifactRemover(signal=_SIGNAL, n_components=10, method="infomax", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            await _KNOT.process(signal="x", n_components=10, method="infomax")  # type: ignore[arg-type]

    async def test_rejects_non_int_components(self) -> None:
        with self.assertRaisesRegex(TypeError, "n_components"):
            await _KNOT.process(signal=_SIGNAL, n_components="x", method="infomax")  # type: ignore[arg-type]

    async def test_rejects_non_positive_components(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            await _KNOT.process(signal=_SIGNAL, n_components=0, method="infomax")

    async def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            await _KNOT.process(signal=_SIGNAL, n_components=10, method="bogus")

    async def test_returns_signal_frame(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, n_components=10, method="fastica")
        assert isinstance(out, SignalFrame)
