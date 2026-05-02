"""Unit tests for :class:`MusicInformationRetriever`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.music_information_retriever import (
    MusicInformationRetriever,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_empty_feature_set(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="non-empty"):
                MusicInformationRetriever(
                    signal=sig,
                    feature_set=(),
                    _config=KnotConfig(id="mir"),
                )

    def test_rejects_unknown_feature(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="unknown feature"):
                MusicInformationRetriever(
                    signal=sig,
                    feature_set=("bogus",),
                    _config=KnotConfig(id="mir"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            MusicInformationRetriever(
                signal=sig,
                feature_set=("chroma", "tempo"),
                _config=KnotConfig(id="mir"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["mir"]
        assert out["feature_set"] == ["chroma", "tempo"]
        assert out["signal_id"] == "test"
