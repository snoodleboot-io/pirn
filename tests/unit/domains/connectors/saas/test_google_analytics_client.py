"""Unit tests for :class:`GoogleAnalyticsClient`.

Uses an injected stub client that mirrors the slice of the
``BetaAnalyticsDataClient`` API we exercise. No real GCP credentials
are required.
"""

from __future__ import annotations

from typing import Any
import unittest

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.saas.google_analytics_client import (
    GoogleAnalyticsClient,
)
from pirn.domains.connectors.saas.google_analytics_config import (
    GoogleAnalyticsConfig,
)


class FakeGoogleAnalyticsClient:
    """Mirrors the BetaAnalyticsDataClient surface we call into."""

    def __init__(self) -> None:
        self.run_report_calls: list[dict[str, Any]] = []
        self.run_realtime_report_calls: list[dict[str, Any]] = []
        self.closed = False

    def run_report(self, request: dict[str, Any]) -> dict[str, Any]:
        self.run_report_calls.append(dict(request))
        return {"rows": [], "request": dict(request)}

    def run_realtime_report(self, request: dict[str, Any]) -> dict[str, Any]:
        self.run_realtime_report_calls.append(dict(request))
        return {"rows": [], "request": dict(request)}

    def close(self) -> None:
        self.closed = True



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            GoogleAnalyticsClient()
    
    
class TestRequestDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_run_report_passes_body(self) -> None:
        fake = FakeGoogleAnalyticsClient()
        client = GoogleAnalyticsClient(client=fake)
        body = {"property": "properties/123", "dateRanges": [{}]}
        result = await client.request("POST", "runReport", body=body)
        assert fake.run_report_calls == [body]
        assert result["request"] == body

    async def test_run_realtime_report_routes_correctly(self) -> None:
        fake = FakeGoogleAnalyticsClient()
        client = GoogleAnalyticsClient(client=fake)
        await client.request(
            "POST", "runRealtimeReport", body={"property": "properties/9"}
        )
        assert fake.run_realtime_report_calls == [
            {"property": "properties/9"}
        ]
        assert fake.run_report_calls == []

    async def test_leading_slash_path_accepted(self) -> None:
        fake = FakeGoogleAnalyticsClient()
        client = GoogleAnalyticsClient(client=fake)
        await client.request("POST", "/runReport", body={"k": "v"})
        assert fake.run_report_calls == [{"k": "v"}]

    async def test_unsupported_path_raises(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        with self.assertRaisesRegex(ValueError, "unsupported path"):
            await client.request("POST", "fetchEverything", body={})

    async def test_empty_method_raises(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        with self.assertRaisesRegex(ValueError, "method must be non-empty"):
            await client.request("", "runReport", body={})

    async def test_empty_path_raises(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        with self.assertRaisesRegex(ValueError, "path must be non-empty"):
            await client.request("POST", "", body={})


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeGoogleAnalyticsClient()
        client = GoogleAnalyticsClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("POST", "runReport", body={})


class TestConfigSafety(unittest.TestCase):
    def test_sensitive_fields_declared(self) -> None:
        assert (
            "service_account_json"
            in GoogleAnalyticsConfig.sensitive_fields
        )

    def test_repr_redacts_service_account_json(self) -> None:
        cfg = GoogleAnalyticsConfig(
            property_id="123456789",
            service_account_json='{"private_key": "leaks"}',
        )
        text = repr(cfg)
        assert "leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_service_account_json(self) -> None:
        cfg = GoogleAnalyticsConfig(
            property_id="123",
            service_account_json='{"private_key": "leaks"}',
        )
        d = cfg.to_audit_dict()
        assert d["service_account_json"] == "<redacted>"
        assert d["property_id"] == "123"


# ────────────────────────────────────────────────────────── capability surface


    def test_implements_table_source(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        assert isinstance(client, TableSource)
    
    
    def test_construction_rejects_non_mapping_report_request(self) -> None:
        with self.assertRaisesRegex(ValueError, "report_request must be a Mapping"):
            GoogleAnalyticsClient(
                client=FakeGoogleAnalyticsClient(),
                report_request=[],  # type: ignore[arg-type]
            )
    
    
    def test_report_request_property_returns_copy(self) -> None:
        request = {"property": "properties/123"}
        client = GoogleAnalyticsClient(
            client=FakeGoogleAnalyticsClient(), report_request=request
        )
        assert client.report_request == {"property": "properties/123"}
    
    
class TestRunReport(unittest.IsolatedAsyncioTestCase):
    async def test_run_report_forwards_body(self) -> None:
        fake = FakeGoogleAnalyticsClient()
        client = GoogleAnalyticsClient(client=fake)

        body = {"property": "properties/9", "dateRanges": [{}]}
        result = await client.run_report(body)

        assert fake.run_report_calls == [body]
        assert result["request"] == body

    async def test_run_report_rejects_non_mapping(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        with self.assertRaisesRegex(ValueError, "must be a Mapping"):
            await client.run_report([])  # type: ignore[arg-type]


class TestFetchPage(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_uses_report_request_with_pagination(self,) -> None:
        fake = FakeGoogleAnalyticsClient()
        fake.run_report = lambda req: {  # type: ignore[method-assign]
            "rows": [{"v": i} for i in range(3)],
            "request": dict(req),
        }
        client = GoogleAnalyticsClient(
            client=fake,
            report_request={"property": "properties/1"},
        )

        rows, next_cursor = await client.fetch_page(page_size=3)

        assert rows == [{"v": 0}, {"v": 1}, {"v": 2}]
        assert next_cursor == "3"

    async def test_fetch_page_full_page_advances_cursor(self) -> None:
        fake = FakeGoogleAnalyticsClient()
        captured: list[dict[str, Any]] = []

        def _run_report(req: dict[str, Any]) -> dict[str, Any]:
            captured.append(dict(req))
            return {"rows": [{"v": i} for i in range(2)]}

        fake.run_report = _run_report  # type: ignore[method-assign]
        client = GoogleAnalyticsClient(
            client=fake,
            report_request={"property": "properties/1"},
        )

        rows, next_cursor = await client.fetch_page(
            cursor="10", page_size=2
        )

        assert rows == [{"v": 0}, {"v": 1}]
        assert next_cursor == "12"
        assert captured[0]["offset"] == 10
        assert captured[0]["limit"] == 2
        assert captured[0]["property"] == "properties/1"

    async def test_fetch_page_partial_terminates(self) -> None:
        fake = FakeGoogleAnalyticsClient()
        fake.run_report = lambda req: {"rows": [{"v": 0}]}  # type: ignore[method-assign]
        client = GoogleAnalyticsClient(
            client=fake,
            report_request={"property": "properties/1"},
        )

        rows, next_cursor = await client.fetch_page(page_size=10)

        assert rows == [{"v": 0}]
        assert next_cursor is None

    async def test_fetch_page_empty_terminates(self) -> None:
        fake = FakeGoogleAnalyticsClient()
        fake.run_report = lambda req: {"rows": []}  # type: ignore[method-assign]
        client = GoogleAnalyticsClient(
            client=fake,
            report_request={"property": "properties/1"},
        )

        rows, next_cursor = await client.fetch_page()

        assert rows == []
        assert next_cursor is None

    async def test_fetch_page_without_report_request_raises(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        with pytest.raises(
            RuntimeError, match="no report_request configured"
        ):
            await client.fetch_page()
