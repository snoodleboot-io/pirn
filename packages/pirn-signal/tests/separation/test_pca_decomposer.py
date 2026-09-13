"""Unit tests for :class:`PCADecomposer`."""

from __future__ import annotations

import unittest

try:
    import sklearn  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("sklearn not installed") from _e

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.separation.pca_decomposer import PCADecomposer
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.source_payload import SourcePayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload(channel_count=8)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestPCADecomposer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> PCADecomposer:
        return PCADecomposer(
            signal=_up(),
            component_count=2,
            _config=KnotConfig(id="pca"),
        )

    async def test_rejects_non_positive_component_count(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="component_count"):
            await knot.process(_SIGNAL, component_count=0)

    async def test_rejects_non_bool_whiten(self) -> None:
        knot = self._make()
        with pytest.raises(TypeError, match="whiten"):
            await knot.process(_SIGNAL, component_count=2, whiten="yes")  # type: ignore[arg-type]

    async def test_emits_source_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, component_count=2)
        assert isinstance(out, SourcePayload)
        assert out.frame.source_count == 2
