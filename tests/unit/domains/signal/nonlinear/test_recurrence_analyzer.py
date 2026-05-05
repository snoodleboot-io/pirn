"""Unit tests for :class:`RecurrenceAnalyzer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.nonlinear.recurrence_analyzer import RecurrenceAnalyzer
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_embedding_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "embedding_dim"):
                RecurrenceAnalyzer(
                    signal=sig,
                    embedding_dim=0,
                    time_delay=1,
                    recurrence_threshold=0.1,
                    _config=KnotConfig(id="r"),
                )

    def test_rejects_non_positive_time_delay(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "time_delay"):
                RecurrenceAnalyzer(
                    signal=sig,
                    embedding_dim=3,
                    time_delay=0,
                    recurrence_threshold=0.1,
                    _config=KnotConfig(id="r"),
                )

    def test_rejects_non_positive_threshold(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "recurrence_threshold"):
                RecurrenceAnalyzer(
                    signal=sig,
                    embedding_dim=3,
                    time_delay=1,
                    recurrence_threshold=0,
                    _config=KnotConfig(id="r"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            RecurrenceAnalyzer(
                signal=sig,
                embedding_dim=3,
                time_delay=1,
                recurrence_threshold=0.1,
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert out["embedding_dim"] == 3
        assert out["recurrence_threshold"] == 0.1
