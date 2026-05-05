"""Unit tests for :class:`ExpressionQuantifier`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.expression_quantifier import (
    ExpressionQuantifier,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_bam(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            ExpressionQuantifier(
                bam_path="",
                annotation_path="g.gtf",
                sample_id="S1",
                _config=KnotConfig(id="q"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_mapping(self) -> None:
        with Tapestry() as t:
            ExpressionQuantifier(
                bam_path="in.bam",
                annotation_path="g.gtf",
                sample_id="S1",
                _config=KnotConfig(id="q"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["q"]
        assert isinstance(out, Mapping)
