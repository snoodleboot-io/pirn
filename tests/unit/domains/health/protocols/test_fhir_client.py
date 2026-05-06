"""Unit tests for :class:`FHIRClient` interface."""

from __future__ import annotations

import unittest

from pirn.domains.health.protocols.fhir_client import FHIRClient


class TestFHIRClientInterface(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_resource_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "fetch_resource"):
            await FHIRClient().fetch_resource("Patient", "1")

    async def test_search_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "search"):
            await FHIRClient().search("Patient", {})

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await FHIRClient().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyClient(FHIRClient):
            pass

        with self.assertRaisesRegex(NotImplementedError, "MyClient"):
            await MyClient().fetch_resource("Patient", "1")
