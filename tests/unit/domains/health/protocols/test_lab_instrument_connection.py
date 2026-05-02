"""Unit tests for :class:`LabInstrumentConnection` interface."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pirn.domains.health.protocols.lab_instrument_connection import (
    LabInstrumentConnection,
)


@pytest.mark.asyncio
class TestLabInstrumentConnectionInterface:
    async def test_fetch_results_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="fetch_results"):
            await LabInstrumentConnection().fetch_results(
                "i1", datetime(2026, 1, 1, tzinfo=timezone.utc)
            )

    async def test_close_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="close"):
            await LabInstrumentConnection().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyConn(LabInstrumentConnection):
            pass

        with pytest.raises(NotImplementedError, match="MyConn"):
            await MyConn().fetch_results(
                "i1", datetime(2026, 1, 1, tzinfo=timezone.utc)
            )
