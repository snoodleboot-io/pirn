"""Unit tests for :class:`GoogleAnalyticsClient`.

Uses an injected stub client that mirrors the slice of the
``BetaAnalyticsDataClient`` API we exercise. No real GCP credentials
are required.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
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


def test_implements_api_client() -> None:
    client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        GoogleAnalyticsClient()


class TestRequestDispatch:
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
        with pytest.raises(ValueError, match="unsupported path"):
            await client.request("POST", "fetchEverything", body={})

    async def test_empty_method_raises(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        with pytest.raises(ValueError, match="method must be non-empty"):
            await client.request("", "runReport", body={})

    async def test_empty_path_raises(self) -> None:
        client = GoogleAnalyticsClient(client=FakeGoogleAnalyticsClient())
        with pytest.raises(ValueError, match="path must be non-empty"):
            await client.request("POST", "", body={})


class TestLifecycle:
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
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("POST", "runReport", body={})


class TestConfigSafety:
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
