"""Unit tests for :class:`ModelLineageTracker`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.lineage_store import LineageStore
from pirn_ml.specializations.production.model_lineage_tracker import (
    ModelLineageTracker,
)


class _StubLineage(LineageStore):
    async def log_event(self, event_type, payload) -> None:
        pass

    async def fetch_lineage(self, model_id):
        return {}

    async def close(self) -> None:
        pass


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_dataset(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ModelLineageTracker(
                    dataset="bad",  # type: ignore[arg-type]
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    model=_KnotStub(_config=KnotConfig(id="m")),
                    report=_KnotStub(_config=KnotConfig(id="r")),
                    lineage=_StubLineage(),
                    _config=KnotConfig(id="mlt"),
                )

    def test_rejects_wrong_lineage_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ModelLineageTracker(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    model=_KnotStub(_config=KnotConfig(id="m")),
                    report=_KnotStub(_config=KnotConfig(id="r")),
                    lineage="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="mlt"),
                )

    def test_valid_construction_registers_knot(self) -> None:
        with Tapestry() as t:
            ModelLineageTracker(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                model=_KnotStub(_config=KnotConfig(id="m")),
                report=_KnotStub(_config=KnotConfig(id="r")),
                lineage=_StubLineage(),
                _config=KnotConfig(id="mlt"),
            )
        self.assertIsNotNone(t._store.get("mlt"))
