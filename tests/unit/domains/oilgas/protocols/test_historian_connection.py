"""Tests for :class:`HistorianConnection` interface contract."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pirn.domains.oilgas.protocols.historian_connection import HistorianConnection


@pytest.mark.asyncio
class TestHistorianConnectionInterface:
    async def test_fetch_tag_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="fetch_tag"):
            await HistorianConnection().fetch_tag(
                "tag", datetime(2026, 1, 1, tzinfo=timezone.utc)
            )

    async def test_close_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="close"):
            await HistorianConnection().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyHistorian(HistorianConnection):
            pass

        with pytest.raises(NotImplementedError, match="MyHistorian"):
            await MyHistorian().close()
