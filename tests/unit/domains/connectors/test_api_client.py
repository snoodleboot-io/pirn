"""Tests for :class:`ApiClient`."""

from __future__ import annotations

import unittest

from pirn.connectors.api_client import ApiClient


class TestApiClientInterface(unittest.IsolatedAsyncioTestCase):
    async def test_request_raises_not_implemented(self) -> None:
        client = ApiClient()
        with self.assertRaises(NotImplementedError):
            await client.request("GET", "/test")

    async def test_close_raises_not_implemented(self) -> None:
        client = ApiClient()
        with self.assertRaises(NotImplementedError):
            await client.close()

    def test_subclass_can_override(self) -> None:
        class ConcreteClient(ApiClient):
            async def request(self, method, path, **kwargs):
                return {"ok": True}

            async def close(self):
                pass

        client = ConcreteClient()
        self.assertIsInstance(client, ApiClient)

    def test_clear_credentials_nulls_config(self) -> None:
        client = ApiClient()
        client._config = "secret"  # type: ignore[attr-defined]
        client._clear_credentials()
        self.assertIsNone(client._config)  # type: ignore[attr-defined]
