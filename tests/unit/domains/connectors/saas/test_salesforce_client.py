"""Unit tests for :class:`SalesforceClient`.

Uses an injected stub client mirroring ``simple_salesforce.Salesforce``'s
``query``/``restful``/``session`` surface. No real Salesforce org needed.
"""

from __future__ import annotations

from typing import Any
import unittest


from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.record_writer import RecordWriter
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.saas.salesforce_client import SalesforceClient
from pirn.domains.connectors.saas.salesforce_config import SalesforceConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeSalesforceSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeSalesforceClient:
    """Mirrors the surface ``SalesforceClient`` calls into."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.restful_calls: list[dict[str, Any]] = []
        self.query_response: dict[str, Any] = {"records": [{"Id": "001"}]}
        self.restful_response: dict[str, Any] = {"ok": True}
        self.session = FakeSalesforceSession()

    def query(self, soql: str) -> dict[str, Any]:
        self.queries.append(soql)
        return self.query_response

    def restful(self, path: str, method: str = "GET", params: dict[str, Any] | None = None, json: dict[str, Any] | None = None,) -> dict[str, Any]:
        self.restful_calls.append(
            {"path": path, "method": method, "params": params, "json": json}
        )
        return self.restful_response


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = SalesforceClient(client=FakeSalesforceClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            SalesforceClient()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = SalesforceConfig()
        assert "password" in cfg.sensitive_fields
        assert "security_token" in cfg.sensitive_fields
        assert "consumer_secret" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────── delegation


class TestRequest(unittest.IsolatedAsyncioTestCase):
    async def test_rest_get_dispatches_to_restful(self) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake)
        result = await client.request(
            "GET", "/services/data/v59.0/sobjects/Account/001", params={"a": 1}
        )
        assert result == fake.restful_response
        assert fake.restful_calls == [
            {
                "path": "/services/data/v59.0/sobjects/Account/001",
                "method": "GET",
                "params": {"a": 1},
                "json": None,
            }
        ]

    async def test_post_passes_body(self) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake)
        result = await client.request(
            "POST",
            "/services/data/v59.0/sobjects/Account",
            body={"Name": "Acme"},
        )
        assert result == fake.restful_response
        assert fake.restful_calls[0]["method"] == "POST"
        assert fake.restful_calls[0]["json"] == {"Name": "Acme"}

    async def test_soql_get_dispatches_to_query(self) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake)
        result = await client.request(
            "GET", "/services/data/v59.0/query", params={"q": "SELECT Id FROM Account"}
        )
        assert result == fake.query_response
        assert fake.queries == ["SELECT Id FROM Account"]
        assert fake.restful_calls == []

    async def test_request_returns_stub_response(self) -> None:
        fake = FakeSalesforceClient()
        fake.restful_response = {"custom": "value"}
        client = SalesforceClient(client=fake)
        result = await client.request("GET", "/foo")
        assert result == {"custom": "value"}


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_session(self) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake)
        await client.close()
        assert fake.session.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = SalesforceClient(client=FakeSalesforceClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = SalesforceClient(client=FakeSalesforceClient())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "/foo")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password_and_token(self) -> None:
        cfg = SalesforceConfig(
            username="alice",
            password="hunter2",
            security_token="topsecret-token",
            consumer_secret="oauth-shh",
        )
        text = repr(cfg)
        assert "hunter2" not in text
        assert "topsecret-token" not in text
        assert "oauth-shh" not in text
        assert "<redacted>" in text


# ───────────────────────────────────────────────────────── capability mixins


    def test_implements_table_source_and_record_writer(self) -> None:
        client = SalesforceClient(client=FakeSalesforceClient())
        assert isinstance(client, TableSource)
        assert isinstance(client, RecordWriter)
    
    
    def test_construction_rejects_empty_soql_query(self) -> None:
        with self.assertRaisesRegex(ValueError, "soql_query"):
            SalesforceClient(client=FakeSalesforceClient(), soql_query="")
    
    
    def test_construction_rejects_empty_sobject_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "sobject_type"):
            SalesforceClient(client=FakeSalesforceClient(), sobject_type="")
    
    
    def test_default_sobject_type_is_account(self) -> None:
        client = SalesforceClient(client=FakeSalesforceClient())
        assert client.sobject_type == "Account"
    
    
class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_initial_done(self) -> None:
        fake = FakeSalesforceClient()
        fake.query_response = {
            "records": [{"Id": "001"}, {"Id": "002"}],
            "done": True,
        }
        client = SalesforceClient(
            client=fake, soql_query="SELECT Id FROM Account"
        )
        rows, cursor = await client.fetch_page()
        assert rows == [{"Id": "001"}, {"Id": "002"}]
        assert cursor is None
        assert fake.queries == ["SELECT Id FROM Account"]

    async def test_fetch_page_returns_next_records_url(self) -> None:
        fake = FakeSalesforceClient()
        fake.query_response = {
            "records": [{"Id": "001"}],
            "done": False,
            "nextRecordsUrl": "/services/data/v59.0/query/01g000-2000",
        }
        client = SalesforceClient(
            client=fake, soql_query="SELECT Id FROM Account"
        )
        rows, cursor = await client.fetch_page()
        assert rows == [{"Id": "001"}]
        assert cursor == "/services/data/v59.0/query/01g000-2000"

    async def test_fetch_page_with_cursor_uses_url_directly(self) -> None:
        fake = FakeSalesforceClient()
        fake.restful_response = {
            "records": [{"Id": "003"}],
            "done": True,
        }
        client = SalesforceClient(
            client=fake, soql_query="SELECT Id FROM Account"
        )
        rows, cursor = await client.fetch_page(
            "/services/data/v59.0/query/01g000-2000"
        )
        assert rows == [{"Id": "003"}]
        assert cursor is None
        # When cursor is supplied, it goes through restful (non-SOQL path)
        assert fake.restful_calls[0]["path"] == (
            "/services/data/v59.0/query/01g000-2000"
        )

    async def test_fetch_page_without_query_or_cursor_raises(self) -> None:
        client = SalesforceClient(client=FakeSalesforceClient())
        with self.assertRaisesRegex(RuntimeError, "no soql_query"):
            await client.fetch_page()


class TestSoqlIterator(unittest.IsolatedAsyncioTestCase):
    async def test_soql_yields_all_rows_across_pages(self) -> None:
        fake = FakeSalesforceClient()
        fake.query_response = {
            "records": [{"Id": "001"}, {"Id": "002"}],
            "done": False,
            "nextRecordsUrl": "/services/data/v59.0/query/next-1",
        }
        fake.restful_response = {
            "records": [{"Id": "003"}],
            "done": True,
        }
        client = SalesforceClient(client=fake)
        collected: list[Any] = []
        async for row in client.soql("SELECT Id FROM Account"):
            collected.append(row)
        assert collected == [{"Id": "001"}, {"Id": "002"}, {"Id": "003"}]

    async def test_soql_rejects_empty_query(self) -> None:
        client = SalesforceClient(client=FakeSalesforceClient())
        with self.assertRaisesRegex(ValueError, "non-empty"):
            async for _ in client.soql(""):
                pass


class TestWriteRecords(unittest.IsolatedAsyncioTestCase):
    async def test_write_records_posts_each_record(self) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake, sobject_type="Contact")
        count = await client.write_records(
            [{"Name": "Alice"}, {"Name": "Bob"}]
        )
        assert count == 2
        assert len(fake.restful_calls) == 2
        assert fake.restful_calls[0]["method"] == "POST"
        assert fake.restful_calls[0]["path"] == "/sobjects/Contact"
        assert fake.restful_calls[0]["json"] == {"Name": "Alice"}
        assert fake.restful_calls[1]["json"] == {"Name": "Bob"}

    async def test_write_records_default_sobject_type_is_account(self,) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake)
        count = await client.write_records([{"Name": "Acme"}])
        assert count == 1
        assert fake.restful_calls[0]["path"] == "/sobjects/Account"

    async def test_write_records_empty_returns_zero(self) -> None:
        fake = FakeSalesforceClient()
        client = SalesforceClient(client=fake)
        count = await client.write_records([])
        assert count == 0
        assert fake.restful_calls == []
