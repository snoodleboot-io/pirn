"""Unit tests for :class:`ConnectorBase` lifecycle using stub doubles."""

from __future__ import annotations

import unittest
from typing import Any

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.credential_ref import CredentialRef


class StubClient:
    """A pooled-client double recording its teardown calls."""

    def __init__(self) -> None:
        self.aclosed = False
        self.closed = False

    async def aclose(self) -> None:
        self.aclosed = True


class SyncStubClient:
    """A pooled-client double exposing only a sync ``close``."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class StubConnector(ConnectorBase):
    """A connector whose ``_create_client`` returns a :class:`StubClient`."""

    def __init__(self, *, credential: CredentialRef | None = None) -> None:
        super().__init__(credential=credential)
        self.create_count = 0

    async def _create_client(self) -> Any:
        self.create_count += 1
        return StubClient()


class SyncStubConnector(ConnectorBase):
    """A connector returning a client with only a sync ``close``."""

    async def _create_client(self) -> Any:
        return SyncStubClient()


class TestConnectorBase(unittest.IsolatedAsyncioTestCase):
    def test_rejects_non_credential_ref(self) -> None:
        with self.assertRaises(TypeError):
            StubConnector(credential="not-a-ref")  # type: ignore[arg-type]

    def test_base_create_client_is_interface_contract(self) -> None:
        connector = ConnectorBase()
        # _pirn_audit_dict works without a client and stays secret-free.
        assert connector._pirn_audit_dict() == {
            "connector": "ConnectorBase",
            "has_credential": False,
        }

    async def test_get_client_constructs_once(self) -> None:
        # Arrange
        connector = StubConnector()

        # Act: multiple awaits.
        first = await connector._get_client()
        second = await connector._get_client()
        third = await connector._get_client()

        # Assert: exactly one construction, same cached instance.
        assert connector.create_count == 1
        assert first is second is third

    async def test_base_create_client_raises_not_implemented(self) -> None:
        connector = ConnectorBase()
        with self.assertRaises(NotImplementedError):
            await connector._get_client()

    async def test_close_releases_client_and_is_idempotent(self) -> None:
        # Arrange
        connector = StubConnector()
        client = await connector._get_client()

        # Act
        await connector.close()

        # Assert: async teardown ran and client reference dropped.
        assert client.aclosed is True
        assert connector._client is None

        # Act: a second close is a safe no-op.
        await connector.close()
        assert connector._client is None

    async def test_close_uses_sync_close_when_no_aclose(self) -> None:
        # Arrange
        connector = SyncStubConnector()
        client = await connector._get_client()

        # Act
        await connector.close()

        # Assert
        assert client.closed is True
        assert connector._client is None

    async def test_close_scrubs_credentials(self) -> None:
        # Arrange
        connector = StubConnector(credential=CredentialRef("secret"))
        assert connector._pirn_audit_dict()["has_credential"] is True

        # Act
        await connector.close()

        # Assert: credential dropped, audit flips to False.
        assert connector._credential is None
        assert connector._pirn_audit_dict()["has_credential"] is False

    def test_clear_credentials_scrubs_without_close(self) -> None:
        # Arrange
        connector = StubConnector(credential=CredentialRef("secret"))

        # Act
        connector._clear_credentials()

        # Assert
        assert connector._credential is None
        assert connector._pirn_audit_dict()["has_credential"] is False

    def test_require_raises_actionable_install_error(self) -> None:
        # Arrange
        connector = StubConnector()

        # Act / Assert
        with self.assertRaises(ImportError) as ctx:
            connector._require("vector", "nope_missing_xyz")
        assert 'pip install "pirn-agents[vector]"' in str(ctx.exception)


if __name__ == "__main__":
    unittest.main()
