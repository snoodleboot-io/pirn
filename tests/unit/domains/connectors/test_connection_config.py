"""Tests for :class:`pirn.domains.connectors.connection_config.ConnectionConfig`."""

from __future__ import annotations

import logging
import unittest
from dataclasses import dataclass
from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class FakePostgresConfig(ConnectionConfig):
    host: str
    port: int
    user: str
    password: str
    database: str
    api_token: str


@connection_config(frozen=True)
class FakeS3Config(ConnectionConfig):
    bucket: str
    region: str
    access_key_id: str
    secret_access_key: str
    signed_url: str
    sensitive_fields: ClassVar[tuple[str, ...]] = ("signed_url",)


@connection_config(frozen=True)
class FakeKafkaConfig(ConnectionConfig):
    bootstrap_servers: str
    sasl_username: str
    sasl_password: str
    group_id: str


class TestReprAndStr(unittest.TestCase):
    def test_repr_redacts_password_field(self) -> None:
        cfg = FakePostgresConfig(
            host="db.example.com",
            port=5432,
            user="alice",
            password="hunter2",
            database="prod",
            api_token="tk-abc-123",
        )
        text = repr(cfg)
        assert "hunter2" not in text
        assert "tk-abc-123" not in text
        assert "<redacted>" in text
        assert "alice" in text
        assert "prod" in text

    def test_str_matches_repr(self) -> None:
        cfg = FakePostgresConfig("h", 1, "u", "p", "d", "t")
        assert str(cfg) == repr(cfg)

    def test_repr_redacts_explicitly_marked_field(self) -> None:
        cfg = FakeS3Config(
            bucket="b",
            region="us-east-1",
            access_key_id="AKIA00",
            secret_access_key="VERY_SECRET",
            signed_url="https://...?Signature=abc",
        )
        text = repr(cfg)
        assert "VERY_SECRET" not in text
        assert "?Signature=abc" not in text

    def test_repr_scrubs_dsn_in_non_sensitive_string_fields(self) -> None:
        @connection_config(frozen=True)
        class WithDsn(ConnectionConfig):
            label: str
            dsn: str

        cfg = WithDsn(label="primary", dsn="postgres://u:p@host/db")
        text = repr(cfg)
        assert "u:p@" not in text
        assert "<redacted>" in text

    def test_fstring_does_not_leak(self) -> None:
        cfg = FakeKafkaConfig(
            bootstrap_servers="kafka:9092",
            sasl_username="alice",
            sasl_password="my-kafka-pw",
            group_id="g1",
        )
        message = f"connecting with {cfg}"
        assert "my-kafka-pw" not in message
        assert "<redacted>" in message


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_redacts_sensitive_fields(self) -> None:
        cfg = FakePostgresConfig("h", 5432, "u", "very-secret-pw", "d", "tok")
        audit = cfg.to_audit_dict()
        assert audit["password"] == "<redacted>"
        assert audit["api_token"] == "<redacted>"
        assert audit["host"] == "h"
        assert audit["port"] == 5432
        assert audit["_class"] == "FakePostgresConfig"

    def test_audit_dict_scrubs_dsn_in_strings(self) -> None:
        @connection_config(frozen=True)
        class WithDsn(ConnectionConfig):
            label: str
            dsn: str

        cfg = WithDsn("primary", "postgres://u:p@host/db")
        audit = cfg.to_audit_dict()
        assert "u:p@" not in audit["dsn"]
        assert "<redacted>" in audit["dsn"]
        assert audit["label"] == "primary"

    def test_audit_dict_includes_class_marker(self) -> None:
        cfg = FakeKafkaConfig("kafka:9092", "alice", "pw", "g1")
        assert cfg.to_audit_dict()["_class"] == "FakeKafkaConfig"


class TestLoggingDoesNotLeak(unittest.TestCase):
    def test_logger_with_config_does_not_leak_password(self) -> None:
        # TODO(unittest-migrate): replace 'caplog' built-in fixture
        # use unittest.mock.patch / assertLogs
        cfg = FakePostgresConfig("h", 5432, "alice", "leaky-pw-1", "d", "tok-2")
        log = logging.getLogger("test.connectors")
        with self.assertLogs(level=logging.DEBUG) as cm:
            log.info("connecting with %s", cfg)
            log.debug("audit=%s", cfg.to_audit_dict())
        rendered = "\n".join(cm.output)
        assert "leaky-pw-1" not in rendered
        assert "tok-2" not in rendered


class TestManualDataclassWithReprFalse(unittest.TestCase):
    """Documented escape hatch: ``@dataclass(repr=False)`` directly."""

    def test_manual_dataclass_repr_false_preserves_redaction(self) -> None:
        @dataclass(frozen=True, repr=False)
        class ManualConfig(ConnectionConfig):
            host: str
            password: str

        cfg = ManualConfig("db.example.com", "shh-do-not-leak")
        assert "shh-do-not-leak" not in repr(cfg)
        assert "<redacted>" in repr(cfg)

    def test_default_dataclass_does_leak_documenting_the_footgun(self) -> None:
        @dataclass(frozen=True)
        class UnsafeConfig(ConnectionConfig):
            host: str
            password: str

        cfg = UnsafeConfig("db.example.com", "this-leaks")
        # Confirms the failure mode rather than asserting safety —
        # users must use @connection_config or @dataclass(repr=False).
        assert "this-leaks" in repr(cfg)
