"""Tests for S6 secret-leak detection/redaction (PIR-271 / PIR-331, PIR-334, PIR-335).

Covers common secret formats (DSNs, AWS keys, JWTs, bearer headers, PEM private
keys, ``key=value`` assignments) across three surfaces: tool arguments, tool
results, and log output. Reuses the pirn-core ``DsnScrubber`` via the scanner and
uses stub doubles / an in-memory log handler — no backend.
"""

from __future__ import annotations

import logging

import pytest

from pirn_agents.security.secret_leak_scanner import SecretLeakScanner
from pirn_agents.security.secret_redacting_log_filter import SecretRedactingLogFilter
from pirn_agents.security.secret_redactor import SecretRedactor

_AWS = "AKIA1234567890ABCDEF"
_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcDEFghijKLMnopQRStuv"
_DSN = "postgres://admin:s3cr3t@db.internal:5432/app"


def test_scanner_reuses_dsn_scrubber() -> None:
    scanner = SecretLeakScanner()
    redacted, kinds = scanner.redact_text(f"connecting to {_DSN}")
    assert "s3cr3t" not in redacted
    assert "dsn" in kinds


@pytest.mark.parametrize(
    ("text", "expected_kind", "secret"),
    [
        (f"key {_AWS} leaked", "aws_key", _AWS),
        (f"token {_JWT}", "jwt", _JWT),
        ("Authorization: Bearer abcdef123456ghijkl", "authorization", "abcdef123456ghijkl"),
        ("api_key = sk-abcdef1234567890", "assignment", "sk-abcdef1234567890"),
    ],
)
def test_scanner_detects_and_redacts_formats(text: str, expected_kind: str, secret: str) -> None:
    redacted, kinds = SecretLeakScanner().redact_text(text)
    assert expected_kind in kinds
    assert secret not in redacted
    assert "<redacted>" in redacted


def test_pem_private_key_redacted() -> None:
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAK...\n-----END RSA PRIVATE KEY-----"
    redacted, kinds = SecretLeakScanner().redact_text(f"pk={pem}")
    assert "private_key" in kinds
    assert "MIIBOgIBAAJBAK" not in redacted


def test_redact_arguments_by_key_name_and_value() -> None:
    # Arrange — a nested tool-arg mapping with a secret-named key and an inline key.
    args = {
        "user": "alice",
        "password": "hunter2",
        "config": {"api_key": "sk-deadbeefdeadbeef", "region": "us"},
        "note": f"dsn {_DSN}",
    }

    # Act
    result = SecretRedactor().redact_arguments(args)

    # Assert — original untouched; copy scrubbed; findings enumerate the leaks.
    assert args["password"] == "hunter2"  # input not mutated
    assert result.value["password"] == "<redacted>"
    assert result.value["config"]["api_key"] == "<redacted>"
    assert result.value["user"] == "alice"
    assert "s3cr3t" not in result.value["note"]
    assert result.leaked
    paths = {finding.path for finding in result.findings}
    assert "args.password" in paths
    assert "args.config.api_key" in paths


def test_redact_result_walks_lists() -> None:
    result = SecretRedactor().redact_result(["ok", f"leaked {_AWS}", {"token": "t0psecret123"}])
    assert _AWS not in result.value[1]
    assert result.value[2]["token"] == "<redacted>"
    assert result.leaked


def test_clean_arguments_report_no_leak() -> None:
    result = SecretRedactor().redact_arguments({"query": "weather in Paris", "limit": 5})
    assert not result.leaked
    assert result.value == {"query": "weather in Paris", "limit": 5}


def test_redact_arguments_rejects_non_mapping() -> None:
    with pytest.raises(TypeError):
        SecretRedactor().redact_arguments(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_log_filter_redacts_before_emit() -> None:
    # Arrange — a logger with an in-memory handler and the redacting filter.
    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    logger = logging.getLogger("pirn_agents.test.secret_leak")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = _Capture()
    logger.addHandler(handler)
    logger.addFilter(SecretRedactingLogFilter())

    # Act — log a secret via a %s argument.
    logger.info("calling api with api_key=%s", "sk-abcdef1234567890")

    # Assert — the emitted message is redacted and the raw secret is gone.
    assert records
    assert "sk-abcdef1234567890" not in records[0]
    assert "<redacted>" in records[0]
    logger.removeHandler(handler)


def test_log_filter_passes_clean_message_unchanged() -> None:
    filt = SecretRedactingLogFilter()
    record = logging.LogRecord("n", logging.INFO, __file__, 1, "just a normal message", None, None)
    assert filt.filter(record) is True
    assert record.getMessage() == "just a normal message"
