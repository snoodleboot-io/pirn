"""Unit tests for :class:`TwilioClient`.

Uses an injected stub client that mirrors the low-level
``Client.request(method, uri, params=, data=, headers=)`` slice. No
real Twilio account needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.record_writer import RecordWriter
from pirn.domains.connectors.saas.twilio_client import TwilioClient
from pirn.domains.connectors.saas.twilio_config import TwilioConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeTwilioClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any, Any, Any]] = []
        self.response: Any = {"sid": "SM123", "status": "queued"}
        self.closed = False

    def request(
        self,
        method: str,
        uri: str,
        params: Any = None,
        data: Any = None,
        headers: Any = None,
    ) -> Any:
        self.calls.append((method, uri, params, data, headers))
        return self.response

    def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_api_client() -> None:
    client = TwilioClient(client=FakeTwilioClient())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        TwilioClient()


def test_sensitive_fields_listed() -> None:
    assert TwilioConfig.sensitive_fields == ("auth_token",)


# ────────────────────────────────────────────────────────────── dispatch


@pytest.mark.asyncio
class TestRequest:
    async def test_request_forwards_to_low_level(self) -> None:
        fake = FakeTwilioClient()
        client = TwilioClient(client=fake)

        result = await client.request(
            "POST",
            "/2010-04-01/Accounts/AC1/Messages.json",
            body={"To": "+15558675309", "Body": "hi"},
        )

        assert result == {"sid": "SM123", "status": "queued"}
        assert fake.calls == [
            (
                "POST",
                "/2010-04-01/Accounts/AC1/Messages.json",
                None,
                {"To": "+15558675309", "Body": "hi"},
                None,
            )
        ]

    async def test_request_passes_params_and_headers(self) -> None:
        fake = FakeTwilioClient()
        client = TwilioClient(client=fake)

        await client.request(
            "GET",
            "/2010-04-01/Accounts/AC1/Messages.json",
            params={"PageSize": 50},
            headers={"X-Trace": "abc"},
        )

        method, uri, params, data, headers = fake.calls[0]
        assert method == "GET"
        assert uri == "/2010-04-01/Accounts/AC1/Messages.json"
        assert params == {"PageSize": 50}
        assert data is None
        assert headers == {"X-Trace": "abc"}


# ─────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeTwilioClient()
        client = TwilioClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = TwilioClient(client=FakeTwilioClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = TwilioClient(client=FakeTwilioClient())
        await client.close()
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "/2010-04-01/Accounts.json")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_auth_token(self) -> None:
        cfg = TwilioConfig(
            account_sid="AC123",
            auth_token="secret-leaks",
        )
        text = repr(cfg)
        assert "secret-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_auth_token(self) -> None:
        cfg = TwilioConfig(
            account_sid="AC123",
            auth_token="secret-leaks",
            region="ie1",
        )
        d = cfg.to_audit_dict()
        assert d["auth_token"] == "<redacted>"
        assert d["account_sid"] == "AC123"
        assert d["region"] == "ie1"


# ────────────────────────────────────────────────────────── capability surface


def test_implements_record_writer() -> None:
    client = TwilioClient(client=FakeTwilioClient())
    assert isinstance(client, RecordWriter)


@pytest.mark.asyncio
class TestSendSms:
    async def test_send_sms_posts_message(self) -> None:
        fake = FakeTwilioClient()
        cfg = TwilioConfig(account_sid="AC1", auth_token="tok")
        client = TwilioClient(config=cfg, client=fake)

        result = await client.send_sms(
            from_number="+15550001",
            to="+15550002",
            body="hello",
        )

        assert result == {"sid": "SM123", "status": "queued"}
        method, uri, params, data, _ = fake.calls[0]
        assert method == "POST"
        assert uri == "/2010-04-01/Accounts/AC1/Messages.json"
        assert params is None
        assert data == {
            "From": "+15550001",
            "To": "+15550002",
            "Body": "hello",
        }

    async def test_send_sms_uses_account_placeholder_without_config(
        self,
    ) -> None:
        fake = FakeTwilioClient()
        client = TwilioClient(client=fake)

        await client.send_sms(
            from_number="+1", to="+2", body="hi"
        )

        _, uri, _, _, _ = fake.calls[0]
        assert uri == "/2010-04-01/Accounts/Account/Messages.json"

    async def test_send_sms_rejects_empty_args(self) -> None:
        client = TwilioClient(client=FakeTwilioClient())
        with pytest.raises(ValueError, match="from_number"):
            await client.send_sms(from_number="", to="+2", body="hi")
        with pytest.raises(ValueError, match="to must be"):
            await client.send_sms(from_number="+1", to="", body="hi")
        with pytest.raises(ValueError, match="body must be"):
            await client.send_sms(from_number="+1", to="+2", body="")


@pytest.mark.asyncio
class TestWriteRecords:
    async def test_write_records_sends_each_message(self) -> None:
        fake = FakeTwilioClient()
        cfg = TwilioConfig(account_sid="AC1", auth_token="tok")
        client = TwilioClient(config=cfg, client=fake)

        count = await client.write_records(
            [
                {"from": "+1", "to": "+2", "body": "hello"},
                {"from": "+1", "to": "+3", "body": "world"},
            ]
        )

        assert count == 2
        assert len(fake.calls) == 2
        _, _, _, data0, _ = fake.calls[0]
        _, _, _, data1, _ = fake.calls[1]
        assert data0 == {"From": "+1", "To": "+2", "Body": "hello"}
        assert data1 == {"From": "+1", "To": "+3", "Body": "world"}

    async def test_write_records_empty_returns_zero(self) -> None:
        fake = FakeTwilioClient()
        cfg = TwilioConfig(account_sid="AC1", auth_token="tok")
        client = TwilioClient(config=cfg, client=fake)

        count = await client.write_records([])

        assert count == 0
        assert fake.calls == []

    async def test_write_records_rejects_missing_keys(self) -> None:
        fake = FakeTwilioClient()
        cfg = TwilioConfig(account_sid="AC1", auth_token="tok")
        client = TwilioClient(config=cfg, client=fake)

        with pytest.raises(ValueError, match="'from', 'to', and 'body'"):
            await client.write_records(
                [{"from": "+1", "to": "+2"}]
            )
