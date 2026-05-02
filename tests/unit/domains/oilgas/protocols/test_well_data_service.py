"""Tests for :class:`WellDataService` interface contract."""

from __future__ import annotations

import pytest

from pirn.domains.oilgas.protocols.well_data_service import WellDataService


@pytest.mark.asyncio
class TestWellDataServiceInterface:
    async def test_fetch_well_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="fetch_well"):
            await WellDataService().fetch_well("W1")

    async def test_list_wells_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="list_wells"):
            await WellDataService().list_wells("F1")

    async def test_close_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="close"):
            await WellDataService().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyService(WellDataService):
            pass

        with pytest.raises(NotImplementedError, match="MyService"):
            await MyService().fetch_well("W1")
