"""Unit tests for :class:`ShadowDeploymentPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.specializations.production.shadow_deployment_pipeline import (
    ShadowDeploymentPipeline,
)
from pirn.tapestry import Tapestry


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
    def test_rejects_non_knot_champion(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ShadowDeploymentPipeline(
                    champion="bad",  # type: ignore[arg-type]
                    challenger=_KnotStub(_config=KnotConfig(id="c")),
                    lineage=_StubLineage(),
                    _config=KnotConfig(id="sdp"),
                )

    def test_rejects_wrong_lineage_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ShadowDeploymentPipeline(
                    champion=_KnotStub(_config=KnotConfig(id="ch")),
                    challenger=_KnotStub(_config=KnotConfig(id="c")),
                    lineage="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="sdp"),
                )

    def test_valid_construction_registers_knot(self) -> None:
        with Tapestry() as t:
            ShadowDeploymentPipeline(
                champion=_KnotStub(_config=KnotConfig(id="ch")),
                challenger=_KnotStub(_config=KnotConfig(id="c")),
                lineage=_StubLineage(),
                _config=KnotConfig(id="sdp"),
            )
        self.assertIsNotNone(t._store.get("sdp"))
