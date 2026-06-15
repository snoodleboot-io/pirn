"""Unit tests for :class:`OMOPConnection` interface."""

from __future__ import annotations

import unittest

from pirn_health.protocols.omop_connection import OMOPConnection


class TestOMOPConnectionInterface(unittest.IsolatedAsyncioTestCase):
    async def test_query_concept_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "query_concept"):
            await OMOPConnection().query_concept(1)

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await OMOPConnection().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyOMOP(OMOPConnection):
            pass

        with self.assertRaisesRegex(NotImplementedError, "MyOMOP"):
            await MyOMOP().query_concept(1)


class TestPoolProperty(unittest.TestCase):
    def test_default_pool_is_none(self) -> None:
        assert OMOPConnection().pool is None
