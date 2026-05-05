"""Unit tests for :class:`MatchedFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.matched_filter import MatchedFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_template(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                MatchedFilter(
                    signal=sig,
                    template=[],
                    _config=KnotConfig(id="m"),
                )

    def test_rejects_non_numeric_template_value(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(TypeError, "real numbers"):
                MatchedFilter(
                    signal=sig,
                    template=[1.0, "x"],  # type: ignore[list-item]
                    _config=KnotConfig(id="m"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            MatchedFilter(
                signal=sig,
                template=[1.0, -1.0, 1.0],
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:matched"
