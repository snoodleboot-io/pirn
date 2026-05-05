"""Unit tests for :class:`ArtifactRemover`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.artifact_remover import ArtifactRemover
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            ArtifactRemover(
                signal="x",  # type: ignore[arg-type]
                n_components=10,
                method="infomax",
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_int_components(self) -> None:
        with self.assertRaisesRegex(TypeError, "n_components"):
            ArtifactRemover(
                signal=SignalFrame(),
                n_components="x",  # type: ignore[arg-type]
                method="infomax",
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_positive_components(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            ArtifactRemover(
                signal=SignalFrame(),
                n_components=0,
                method="infomax",
                _config=KnotConfig(id="r"),
            )

    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            ArtifactRemover(
                signal=SignalFrame(),
                n_components=10,
                method="bogus",
                _config=KnotConfig(id="r"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_signal_frame(self) -> None:
        with Tapestry() as t:
            ArtifactRemover(
                signal=SignalFrame(signal_id="s"),
                n_components=10,
                method="fastica",
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert isinstance(out, SignalFrame)
