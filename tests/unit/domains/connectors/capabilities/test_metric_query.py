"""Tests for :class:`MetricQuery`."""

from __future__ import annotations

import unittest

from pirn.connectors.capabilities.metric_query import MetricQuery


class TestMetricQueryInterface(unittest.IsolatedAsyncioTestCase):
    async def test_query_raises_not_implemented(self) -> None:
        mq = MetricQuery()
        with self.assertRaises(NotImplementedError):
            await mq.query("up")
