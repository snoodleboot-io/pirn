"""Unit tests for :class:`LabInstrumentConnection` interface."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.domains.health.protocols.lab_instrument_connection import (
    LabInstrumentConnection,
)


class TestLabInstrumentConnectionInterface(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_results_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "fetch_results"):
            await LabInstrumentConnection().fetch_results(
                "i1", datetime(2026, 1, 1, tzinfo=UTC)
            )

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await LabInstrumentConnection().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyConn(LabInstrumentConnection):
            pass

        with self.assertRaisesRegex(NotImplementedError, "MyConn"):
            await MyConn().fetch_results(
                "i1", datetime(2026, 1, 1, tzinfo=UTC)
            )
