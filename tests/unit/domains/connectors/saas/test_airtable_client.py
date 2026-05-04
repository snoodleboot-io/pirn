"""Unit tests for :class:`AirtableClient`.

Uses an injected stub httpx client. No network needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.saas.airtable_client import AirtableClient
from pirn.domains.connectors.saas.airtable_config import AirtableConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeHTTPXClient:
    """Minimal httpx.AsyncClient stub for :class:`AirtableClient`."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._responses: dict[str, Any] = {}
        self.default_response: dict[str, Any] = {"records": []}
        self.closed = False

    def set_response(self, method: str, response: dict) -> None:
        self._responses[method.upper()] = response

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._responses.get(method.upper(), self.default_response)

    async def aclose(self) -> None:
        self.closed = True


def _make_config(**kwargs: Any) -> AirtableConfig:
    defaults = {
        "api_key": "patXXXXXXXXXXXXXX",
        "base_id": "appXXXXXXXXXXXXXX",
        "table_name": "Tasks",
    }
    defaults.update(kwargs)
    return AirtableConfig(**defaults)


# ───────────────────────────────────────────────────────────── conformance


def test_implements_api_client() -> None:
    client = AirtableClient(client=FakeHTTPXClient())
    assert isinstance(client, ApiClient)


def test_implements_table_source() -> None:
    client = AirtableClient(client=FakeHTTPXClient())
    assert isinstance(client, TableSource)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        AirtableClient()


def test_sensitive_fields_declared() -> None:
    cfg = _make_config()
    assert "api_key" in cfg.sensitive_fields


# ────────────────────────────────────────────────────────────── validation


@pytest.mark.asyncio
class TestValidation:
    async def test_missing_api_key_raises_on_list(self) -> None:
        cfg = AirtableConfig(api_key="", base_id="appXX", table_name="Tasks")
        client = AirtableClient(config=cfg, client=FakeHTTPXClient())
        with pytest.raises(ValueError, match="api_key"):
            await client.list_records()

    async def test_missing_base_id_raises_on_list(self) -> None:
        cfg = AirtableConfig(api_key="pat", base_id="", table_name="Tasks")
        client = AirtableClient(config=cfg, client=FakeHTTPXClient())
        with pytest.raises(ValueError, match="base_id"):
            await client.list_records()

    async def test_missing_table_name_raises_on_list(self) -> None:
        cfg = AirtableConfig(api_key="pat", base_id="appXX", table_name="")
        client = AirtableClient(config=cfg, client=FakeHTTPXClient())
        with pytest.raises(ValueError, match="table_name"):
            await client.list_records()


# ────────────────────────────────────────────────────────────── list_records


@pytest.mark.asyncio
class TestListRecords:
    async def test_list_records_returns_records(self) -> None:
        fake = FakeHTTPXClient()
        fake.set_response(
            "GET",
            {"records": [{"id": "recABC", "fields": {"Name": "Task 1"}}]},
        )
        cfg = _make_config()
        client = AirtableClient(config=cfg, client=fake)
        records, next_offset = await client.list_records()
        assert len(records) == 1
        assert records[0]["id"] == "recABC"
        assert next_offset is None

    async def test_list_records_returns_next_offset(self) -> None:
        fake = FakeHTTPXClient()
        fake.set_response(
            "GET",
            {
                "records": [{"id": "recABC", "fields": {}}],
                "offset": "itrXXXXXXXXXXXXXX",
            },
        )
        cfg = _make_config()
        client = AirtableClient(config=cfg, client=fake)
        _, next_offset = await client.list_records()
        assert next_offset == "itrXXXXXXXXXXXXXX"

    async def test_list_records_passes_offset_param(self) -> None:
        fake = FakeHTTPXClient()
        cfg = _make_config()
        client = AirtableClient(config=cfg, client=fake)
        await client.list_records(offset="itrXXXXXX")
        params = fake.calls[0].get("params") or {}
        assert params.get("offset") == "itrXXXXXX"

    async def test_list_records_url_contains_base_and_table(self) -> None:
        fake = FakeHTTPXClient()
        cfg = _make_config(base_id="appTEST", table_name="MyTable")
        client = AirtableClient(config=cfg, client=fake)
        await client.list_records()
        url = fake.calls[0]["url"]
        assert "appTEST" in url
        assert "MyTable" in url


# ────────────────────────────────────────────────────────────── create_record


@pytest.mark.asyncio
class TestCreateRecord:
    async def test_create_record_posts_fields(self) -> None:
        fake = FakeHTTPXClient()
        fake.set_response("POST", {"id": "recNEW", "fields": {"Name": "New Task"}})
        cfg = _make_config()
        client = AirtableClient(config=cfg, client=fake)
        result = await client.create_record({"Name": "New Task"})
        assert result["id"] == "recNEW"
        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["json"]["fields"] == {"Name": "New Task"}


# ────────────────────────────────────────────────────────────── update_record


@pytest.mark.asyncio
class TestUpdateRecord:
    async def test_update_record_patches_fields(self) -> None:
        fake = FakeHTTPXClient()
        fake.set_response("PATCH", {"id": "recABC", "fields": {"Status": "Done"}})
        cfg = _make_config()
        client = AirtableClient(config=cfg, client=fake)
        result = await client.update_record("recABC", {"Status": "Done"})
        assert result["id"] == "recABC"
        assert fake.calls[0]["method"] == "PATCH"
        assert "recABC" in fake.calls[0]["url"]
        assert fake.calls[0]["json"]["fields"] == {"Status": "Done"}


# ────────────────────────────────────────────────────────────── delete_record


@pytest.mark.asyncio
class TestDeleteRecord:
    async def test_delete_record_sends_delete(self) -> None:
        fake = FakeHTTPXClient()
        fake.set_response("DELETE", {"id": "recABC", "deleted": True})
        cfg = _make_config()
        client = AirtableClient(config=cfg, client=fake)
        result = await client.delete_record("recABC")
        assert result["deleted"] is True
        assert fake.calls[0]["method"] == "DELETE"
        assert "recABC" in fake.calls[0]["url"]


# ────────────────────────────────────────────────────────────── fetch_page


@pytest.mark.asyncio
class TestFetchPage:
    async def test_fetch_page_delegates_to_list_records(self) -> None:
        fake = FakeHTTPXClient()
        fake.set_response(
            "GET",
            {
                "records": [{"id": "recABC", "fields": {}}],
                "offset": "itrNEXT",
            },
        )
        cfg = _make_config()
        client = AirtableClient(config=cfg, client=fake)
        records, next_cursor = await client.fetch_page(cursor=None, page_size=10)
        assert len(records) == 1
        assert next_cursor == "itrNEXT"

    async def test_fetch_page_forwards_cursor(self) -> None:
        fake = FakeHTTPXClient()
        cfg = _make_config()
        client = AirtableClient(config=cfg, client=fake)
        await client.fetch_page(cursor="itrXXXXX")
        params = fake.calls[0].get("params") or {}
        assert params.get("offset") == "itrXXXXX"


# ────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_calls_aclose(self) -> None:
        fake = FakeHTTPXClient()
        client = AirtableClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = AirtableClient(client=FakeHTTPXClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = AirtableClient(client=FakeHTTPXClient())
        await client.close()
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/v0/appXX/Table")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_api_key(self) -> None:
        cfg = _make_config(api_key="patSECRETKEY12345")
        text = repr(cfg)
        assert "patSECRETKEY12345" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_api_key(self) -> None:
        cfg = _make_config(api_key="patSECRETKEY12345")
        d = cfg.to_audit_dict()
        assert d["api_key"] == "<redacted>"
        assert "patSECRETKEY12345" not in str(d)


@pytest.mark.asyncio
class TestSecurity:
    async def test_close_clears_credentials(self) -> None:
        client = AirtableClient(config=_make_config(), client=FakeHTTPXClient())
        assert client._config is not None
        await client.close()
        assert client._config is None

    async def test_use_after_close_raises(self) -> None:
        client = AirtableClient(config=_make_config(), client=FakeHTTPXClient())
        await client.close()
        with pytest.raises(RuntimeError, match="closed"):
            await client.list_records()
