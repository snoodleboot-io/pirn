"""Unit tests for :class:`MixpanelClient`.

Uses an injected stub client that mirrors the slice of the
``mixpanel.Mixpanel`` API we exercise.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.saas.mixpanel_client import MixpanelClient
from pirn.domains.connectors.saas.mixpanel_config import MixpanelConfig


class FakeMixpanelClient:
    """Mirrors the ``mixpanel.Mixpanel`` surface ``MixpanelClient`` calls."""

    def __init__(self) -> None:
        self.tracked: list[tuple[str, str, dict[str, Any]]] = []
        self.imported: list[dict[str, Any]] = []
        self.closed = False

    def track(self, distinct_id: str, event: str, properties: dict[str, Any]) -> None:
        self.tracked.append((distinct_id, event, dict(properties)))

    def import_data(self, **kwargs: Any) -> dict[str, Any]:
        self.imported.append(dict(kwargs))
        return {"status": 1}

    def close(self) -> None:
        self.closed = True



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = MixpanelClient(client=FakeMixpanelClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            MixpanelClient()
    
    
class TestRequestDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_track_routes_to_track(self) -> None:
        fake = FakeMixpanelClient()
        client = MixpanelClient(client=fake)
        body = {
            "distinct_id": "u1",
            "event": "signup",
            "properties": {"plan": "pro"},
        }
        await client.request("POST", "/track", body=body)
        assert fake.tracked == [("u1", "signup", {"plan": "pro"})]

    async def test_track_without_leading_slash(self) -> None:
        fake = FakeMixpanelClient()
        client = MixpanelClient(client=fake)
        await client.request(
            "POST",
            "track",
            body={"distinct_id": "u2", "event": "click"},
        )
        assert fake.tracked == [("u2", "click", {})]

    async def test_track_requires_distinct_id_and_event(self) -> None:
        client = MixpanelClient(client=FakeMixpanelClient())
        with self.assertRaisesRegex(ValueError, "distinct_id"):
            await client.request("POST", "/track", body={"event": "x"})
        with self.assertRaisesRegex(ValueError, "distinct_id"):
            await client.request(
                "POST", "/track", body={"distinct_id": "u"}
            )

    async def test_import_routes_to_import_data(self) -> None:
        fake = FakeMixpanelClient()
        client = MixpanelClient(client=fake)
        await client.request(
            "POST", "/import", body={"events": [{"event": "x"}]}
        )
        assert fake.imported == [{"events": [{"event": "x"}]}]

    async def test_unsupported_path_raises(self) -> None:
        client = MixpanelClient(client=FakeMixpanelClient())
        with self.assertRaisesRegex(ValueError, "unsupported path"):
            await client.request("POST", "/people/set", body={})

    async def test_non_post_method_raises(self) -> None:
        client = MixpanelClient(client=FakeMixpanelClient())
        with self.assertRaisesRegex(ValueError, "only POST"):
            await client.request("GET", "/track", body={})

    async def test_empty_method_raises(self) -> None:
        client = MixpanelClient(client=FakeMixpanelClient())
        with self.assertRaisesRegex(ValueError, "method must be non-empty"):
            await client.request("", "/track", body={})

    async def test_empty_path_raises(self) -> None:
        client = MixpanelClient(client=FakeMixpanelClient())
        with self.assertRaisesRegex(ValueError, "path must be non-empty"):
            await client.request("POST", "", body={})


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeMixpanelClient()
        client = MixpanelClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = MixpanelClient(client=FakeMixpanelClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = MixpanelClient(client=FakeMixpanelClient())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request(
                "POST",
                "/track",
                body={"distinct_id": "u", "event": "e"},
            )


class TestConfigSafety(unittest.TestCase):
    def test_sensitive_fields_declared(self) -> None:
        sensitive = MixpanelConfig.sensitive_fields
        assert "project_token" in sensitive
        assert "api_secret" in sensitive
        assert "service_account_secret" in sensitive

    def test_repr_redacts_secrets(self) -> None:
        cfg = MixpanelConfig(
            project_token="tok-leaks",
            api_secret="sec-leaks",
            service_account_username="svc-user",
            service_account_secret="svc-sec-leaks",
        )
        text = repr(cfg)
        assert "tok-leaks" not in text
        assert "sec-leaks" not in text
        assert "svc-sec-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_secrets(self) -> None:
        cfg = MixpanelConfig(
            project_token="tok",
            api_secret="sec",
            service_account_username="svc-user",
            service_account_secret="svc-sec",
        )
        d = cfg.to_audit_dict()
        assert d["project_token"] == "<redacted>"
        assert d["api_secret"] == "<redacted>"
        assert d["service_account_secret"] == "<redacted>"
        assert d["service_account_username"] == "svc-user"
