"""Unit tests for :class:`AmplitudeClient`.

Uses an injected stub client that mirrors the slice of the
``amplitude.Amplitude`` API we exercise. The ``BaseEvent`` constructor
is satisfied by stubbing the ``amplitude`` module in :data:`sys.modules`,
so the real ``amplitude-analytics`` SDK is not required.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.saas.amplitude_config import AmplitudeConfig


@dataclass
class FakeBaseEvent:
    event_type: str
    user_id: str | None = None
    event_properties: dict[str, Any] | None = None


class FakeAmplitudeClient:
    """Mirrors the ``amplitude.Amplitude`` surface we call into."""

    def __init__(self) -> None:
        self.tracked: list[FakeBaseEvent] = []
        self.flushed = 0
        self.shutdown_called = False

    def track(self, event: FakeBaseEvent) -> None:
        self.tracked.append(event)

    def flush(self) -> None:
        self.flushed += 1

    def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.fixture(autouse=True)
def _stub_amplitude_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a fake ``amplitude`` module so ``BaseEvent`` can be imported."""
    fake_module = types.ModuleType("amplitude")
    fake_module.BaseEvent = FakeBaseEvent  # type: ignore[attr-defined]
    fake_module.Amplitude = FakeAmplitudeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "amplitude", fake_module)


# Imported AFTER the autouse fixture would patch sys.modules, but module
# import in pirn is lazy inside ``_build_event`` / ``_create_client`` so
# importing the connector here is safe regardless of fixture ordering.
from pirn.domains.connectors.saas.amplitude_client import (  # noqa: E402
    AmplitudeClient,
)


def test_implements_api_client() -> None:
    client = AmplitudeClient(client=FakeAmplitudeClient())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        AmplitudeClient()


class TestRequestDispatch:
    async def test_track_builds_base_event(self) -> None:
        fake = FakeAmplitudeClient()
        client = AmplitudeClient(client=fake)
        await client.request(
            "POST",
            "/track",
            body={
                "event": "signup",
                "user_id": "u1",
                "properties": {"plan": "pro"},
            },
        )
        assert len(fake.tracked) == 1
        event = fake.tracked[0]
        assert event.event_type == "signup"
        assert event.user_id == "u1"
        assert event.event_properties == {"plan": "pro"}

    async def test_track_minimal_body(self) -> None:
        fake = FakeAmplitudeClient()
        client = AmplitudeClient(client=fake)
        await client.request("POST", "track", body={"event": "open"})
        assert fake.tracked[0].event_type == "open"
        assert fake.tracked[0].user_id is None
        assert fake.tracked[0].event_properties is None

    async def test_track_requires_event(self) -> None:
        client = AmplitudeClient(client=FakeAmplitudeClient())
        with pytest.raises(ValueError, match="'event'"):
            await client.request("POST", "/track", body={"user_id": "u"})

    async def test_unsupported_path_raises(self) -> None:
        client = AmplitudeClient(client=FakeAmplitudeClient())
        with pytest.raises(ValueError, match="unsupported path"):
            await client.request("POST", "/identify", body={})

    async def test_non_post_method_raises(self) -> None:
        client = AmplitudeClient(client=FakeAmplitudeClient())
        with pytest.raises(ValueError, match="only POST"):
            await client.request("GET", "/track", body={"event": "x"})

    async def test_empty_method_raises(self) -> None:
        client = AmplitudeClient(client=FakeAmplitudeClient())
        with pytest.raises(ValueError, match="method must be non-empty"):
            await client.request("", "/track", body={"event": "x"})

    async def test_empty_path_raises(self) -> None:
        client = AmplitudeClient(client=FakeAmplitudeClient())
        with pytest.raises(ValueError, match="path must be non-empty"):
            await client.request("POST", "", body={"event": "x"})


class TestLifecycle:
    async def test_close_flushes_and_shuts_down(self) -> None:
        fake = FakeAmplitudeClient()
        client = AmplitudeClient(client=fake)
        await client.close()
        assert fake.flushed == 1
        assert fake.shutdown_called is True

    async def test_close_is_idempotent(self) -> None:
        client = AmplitudeClient(client=FakeAmplitudeClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = AmplitudeClient(client=FakeAmplitudeClient())
        await client.close()
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("POST", "/track", body={"event": "x"})


class TestConfigSafety:
    def test_sensitive_fields_declared(self) -> None:
        sensitive = AmplitudeConfig.sensitive_fields
        assert "api_key" in sensitive
        assert "secret_key" in sensitive

    def test_repr_redacts_secrets(self) -> None:
        cfg = AmplitudeConfig(api_key="key-leaks", secret_key="sec-leaks")
        text = repr(cfg)
        assert "key-leaks" not in text
        assert "sec-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_secrets(self) -> None:
        cfg = AmplitudeConfig(api_key="k", secret_key="s")
        d = cfg.to_audit_dict()
        assert d["api_key"] == "<redacted>"
        assert d["secret_key"] == "<redacted>"
