"""Unit tests for :class:`FHIRClient` interface."""

from __future__ import annotations

import pytest

from pirn.domains.health.protocols.fhir_client import FHIRClient


@pytest.mark.asyncio
class TestFHIRClientInterface:
    async def test_fetch_resource_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="fetch_resource"):
            await FHIRClient().fetch_resource("Patient", "1")

    async def test_search_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="search"):
            await FHIRClient().search("Patient", {})

    async def test_close_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="close"):
            await FHIRClient().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyClient(FHIRClient):
            pass

        with pytest.raises(NotImplementedError, match="MyClient"):
            await MyClient().fetch_resource("Patient", "1")
