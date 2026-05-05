"""Tests for :class:`HistorianConnection` interface contract."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest


from pirn.domains.oilgas.protocols.historian_connection import HistorianConnection


class TestHistorianConnectionInterface(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_tag_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "fetch_tag"):
            await HistorianConnection().fetch_tag(
                "tag", datetime(2026, 1, 1, tzinfo=timezone.utc)
            )

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await HistorianConnection().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyHistorian(HistorianConnection):
            pass

        with self.assertRaisesRegex(NotImplementedError, "MyHistorian"):
            await MyHistorian().close()
