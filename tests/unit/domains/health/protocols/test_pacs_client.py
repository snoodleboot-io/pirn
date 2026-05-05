"""Unit tests for :class:`PACSClient` interface."""

from __future__ import annotations
import unittest


from pirn.domains.health.protocols.pacs_client import PACSClient


class TestPACSClientInterface(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_series_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "fetch_series"):
            await PACSClient().fetch_series("ST", "SE")

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await PACSClient().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyPACS(PACSClient):
            pass

        with self.assertRaisesRegex(NotImplementedError, "MyPACS"):
            await MyPACS().fetch_series("ST", "SE")
