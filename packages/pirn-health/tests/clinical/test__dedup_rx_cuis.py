"""Tests for :class:`_DedupRxCUIs`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_health.clinical._dedup_rx_cuis import _DedupRxCUIs


class TestDedupRxCUIsConstruction(unittest.TestCase):
    def test_construction(self) -> None:
        knot = _DedupRxCUIs(
            rxcuis=("123", "456"),
            _config=KnotConfig(id="dedup"),
        )
        self.assertIsInstance(knot, _DedupRxCUIs)


class TestDedupRxCUIsProcess(unittest.IsolatedAsyncioTestCase):
    async def test_deduplicates_rxcuis(self) -> None:
        knot = _DedupRxCUIs(
            rxcuis=("123",),
            _config=KnotConfig(id="dedup"),
        )
        result = await knot.process(rxcuis=("123", "456", "123", "789"), **{})
        self.assertEqual(result, ("123", "456", "789"))

    async def test_preserves_order(self) -> None:
        knot = _DedupRxCUIs(
            rxcuis=("a",),
            _config=KnotConfig(id="dedup"),
        )
        result = await knot.process(rxcuis=("c", "a", "b", "a"), **{})
        self.assertEqual(result, ("c", "a", "b"))

    async def test_filters_empty_strings(self) -> None:
        knot = _DedupRxCUIs(
            rxcuis=("a",),
            _config=KnotConfig(id="dedup"),
        )
        result = await knot.process(rxcuis=("a", "", "b", ""), **{})
        self.assertEqual(result, ("a", "b"))

    async def test_empty_input_returns_empty(self) -> None:
        knot = _DedupRxCUIs(
            rxcuis=(),
            _config=KnotConfig(id="dedup"),
        )
        result = await knot.process(rxcuis=(), **{})
        self.assertEqual(result, ())
