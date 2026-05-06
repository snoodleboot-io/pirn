"""Unit tests for :class:`MusicInformationRetriever`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.audio.music_information_retriever import MusicInformationRetriever
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestMusicInformationRetriever(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> MusicInformationRetriever:
        return MusicInformationRetriever(
            signal=_up(),
            feature_set=("chroma", "tempo"),
            _config=KnotConfig(id="mir"),
        )

    async def test_rejects_empty_feature_set(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="feature_set"):
            await knot.process(_SIGNAL, feature_set=())

    async def test_rejects_unknown_feature(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError):
            await knot.process(_SIGNAL, feature_set=("unknown",))

    async def test_emits_mapping(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, feature_set=("chroma", "tempo"))
        assert isinstance(out, dict)
        assert "feature_set" in out
        assert "chroma" in out["feature_set"]
