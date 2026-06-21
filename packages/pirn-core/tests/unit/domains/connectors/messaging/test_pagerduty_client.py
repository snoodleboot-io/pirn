"""Unit tests for :class:`PagerDutyClient`.

Uses an injected stub httpx client. No network needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.messaging.pagerduty_client import PagerDutyClient
from pirn.connectors.messaging.pagerduty_config import PagerDutyConfig

# ──────────────────────────────────────────────────────────── fake client


class FakeHTTPXClient:
    """Minimal httpx.AsyncClient stub for :class:`PagerDutyClient`."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.post_response: dict[str, Any] = {"status": "success", "dedup_key": "abc123"}
        self.get_response: dict[str, Any] = {"incidents": [{"id": "P1", "status": "triggered"}]}
        self.closed = False

    async def post(self, url: str, **kwargs: Any) -> dict:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.post_response

    async def request(self, method: str, url: str, **kwargs: Any) -> dict:
        self.calls.append({"method": method, "url": url, **kwargs})
        if method == "GET":
            return self.get_response
        return self.post_response

    async def aclose(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = PagerDutyClient(client=FakeHTTPXClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            PagerDutyClient()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = PagerDutyConfig(api_key="key", routing_key="rkey")
        assert "api_key" in cfg.sensitive_fields
        assert "routing_key" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────────── severity validation


class TestSeverityValidation(unittest.IsolatedAsyncioTestCase):
    async def test_valid_severities_accepted(self) -> None:
        fake = FakeHTTPXClient()
        cfg = PagerDutyConfig(api_key="key", routing_key="rkey")
        client = PagerDutyClient(config=cfg, client=fake)
        for sev in ("critical", "error", "warning", "info"):
            await client.trigger_incident("summary", "source", severity=sev)

    async def test_invalid_severity_raises(self) -> None:
        fake = FakeHTTPXClient()
        cfg = PagerDutyConfig(api_key="key", routing_key="rkey")
        client = PagerDutyClient(config=cfg, client=fake)
        with self.assertRaisesRegex(ValueError, "severity"):
            await client.trigger_incident("summary", "source", severity="urgent")


# ────────────────────────────────────────────────────────────── trigger_incident


class TestTriggerIncident(unittest.IsolatedAsyncioTestCase):
    async def test_trigger_posts_to_events_api(self) -> None:
        fake = FakeHTTPXClient()
        cfg = PagerDutyConfig(api_key="key", routing_key="rkey")
        client = PagerDutyClient(config=cfg, client=fake)
        result = await client.trigger_incident("Disk full", "server-01", severity="error")
        assert result == {"status": "success", "dedup_key": "abc123"}
        assert fake.calls[0]["url"] == "https://events.pagerduty.com/v2/enqueue"
        payload = fake.calls[0]["json"]
        assert payload["event_action"] == "trigger"
        assert payload["payload"]["summary"] == "Disk full"
        assert payload["payload"]["source"] == "server-01"
        assert payload["payload"]["severity"] == "error"

    async def test_trigger_with_dedup_key(self) -> None:
        fake = FakeHTTPXClient()
        cfg = PagerDutyConfig(api_key="key", routing_key="rkey")
        client = PagerDutyClient(config=cfg, client=fake)
        await client.trigger_incident("Alert", "host", dedup_key="my-dedup")
        assert fake.calls[0]["json"]["dedup_key"] == "my-dedup"


# ────────────────────────────────────────────────────────────── resolve_incident


class TestResolveIncident(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_posts_resolve_action(self) -> None:
        fake = FakeHTTPXClient()
        cfg = PagerDutyConfig(api_key="key", routing_key="rkey")
        client = PagerDutyClient(config=cfg, client=fake)
        await client.resolve_incident("my-dedup")
        payload = fake.calls[0]["json"]
        assert payload["event_action"] == "resolve"
        assert payload["dedup_key"] == "my-dedup"


# ────────────────────────────────────────────────────────────── list_incidents


class TestListIncidents(unittest.IsolatedAsyncioTestCase):
    async def test_list_incidents_returns_list(self) -> None:
        fake = FakeHTTPXClient()
        cfg = PagerDutyConfig(api_key="key", routing_key="rkey", base_url="https://api.pagerduty.com")
        client = PagerDutyClient(config=cfg, client=fake)
        incidents = await client.list_incidents()
        assert isinstance(incidents, list)
        assert incidents[0]["id"] == "P1"

    async def test_list_incidents_uses_rest_api(self) -> None:
        fake = FakeHTTPXClient()
        cfg = PagerDutyConfig(api_key="key", routing_key="rkey", base_url="https://api.pagerduty.com")
        client = PagerDutyClient(config=cfg, client=fake)
        await client.list_incidents(status="acknowledged", limit=10)
        assert fake.calls[0]["method"] == "GET"
        assert "incidents" in fake.calls[0]["url"]


# ────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_calls_aclose(self) -> None:
        fake = FakeHTTPXClient()
        client = PagerDutyClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = PagerDutyClient(client=FakeHTTPXClient())
        await client.close()
        await client.close()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_api_key(self) -> None:
        cfg = PagerDutyConfig(api_key="supersecretapikey", routing_key="routingkey123")
        text = repr(cfg)
        assert "supersecretapikey" not in text
        assert "routingkey123" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_api_key(self) -> None:
        cfg = PagerDutyConfig(api_key="supersecretapikey", routing_key="routingkey123")
        d = cfg.to_audit_dict()
        assert d["api_key"] == "<redacted>"
        assert d["routing_key"] == "<redacted>"
        assert "supersecretapikey" not in str(d)
        assert "routingkey123" not in str(d)


class TestSecurity(unittest.IsolatedAsyncioTestCase):
    async def test_close_clears_credentials(self) -> None:
        client = PagerDutyClient(
            config=PagerDutyConfig(api_key="key", routing_key="rkey"),
            client=FakeHTTPXClient(),
        )
        assert client._config is not None
        await client.close()
        assert client._config is None

    async def test_use_after_close_raises(self) -> None:
        client = PagerDutyClient(
            config=PagerDutyConfig(api_key="key", routing_key="rkey"),
            client=FakeHTTPXClient(),
        )
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.trigger_incident("Disk full", "server-01")
