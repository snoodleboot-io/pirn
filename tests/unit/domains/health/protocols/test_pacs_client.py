"""Unit tests for :class:`PACSClient` interface."""

from __future__ import annotations

import pytest

from pirn.domains.health.protocols.pacs_client import PACSClient


@pytest.mark.asyncio
class TestPACSClientInterface:
    async def test_fetch_series_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="fetch_series"):
            await PACSClient().fetch_series("ST", "SE")

    async def test_close_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="close"):
            await PACSClient().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyPACS(PACSClient):
            pass

        with pytest.raises(NotImplementedError, match="MyPACS"):
            await MyPACS().fetch_series("ST", "SE")
