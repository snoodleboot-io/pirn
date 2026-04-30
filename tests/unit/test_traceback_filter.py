"""Tests for M-5 (EmitterErrorPolicy) and M-7 (traceback_filter)."""

from __future__ import annotations

import logging

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
from pirn.managers.exception_manager import ExceptionManager
from pirn.managers.redact import redact_common_secrets

# ---------------------------------------------------------------------------
# redact_common_secrets
# ---------------------------------------------------------------------------


def test_redact_dsn_credentials() -> None:
    text = "connecting to postgresql://user:s3cr3t@db.host:5432/mydb"
    result = redact_common_secrets(text)
    assert "s3cr3t" not in result
    assert "postgresql://<redacted>@db.host:5432/mydb" in result


def test_redact_password_assignment() -> None:
    text = "RuntimeError: password=s3cr3t was wrong"
    result = redact_common_secrets(text)
    assert "s3cr3t" not in result
    assert "password=<redacted>" in result


def test_redact_authorization_bearer() -> None:
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
    result = redact_common_secrets(text)
    assert "eyJhbGciOiJIUzI1NiJ9" not in result
    assert "<redacted>" in result


def test_redact_api_key_assignment() -> None:
    text = "api_key=abc123secret was rejected"
    result = redact_common_secrets(text)
    assert "abc123secret" not in result
    assert "<redacted>" in result


def test_redact_leaves_safe_text_unchanged() -> None:
    text = "ValueError: expected 42 but got 43"
    assert redact_common_secrets(text) == text


# ---------------------------------------------------------------------------
# ExceptionManager with traceback_filter
# ---------------------------------------------------------------------------


def test_exception_manager_applies_filter() -> None:
    def my_filter(text: str) -> str:
        return text.replace("secret", "REDACTED")

    mgr = ExceptionManager(run_id="run-1", traceback_filter=my_filter)
    exc = ValueError("secret value leaked")
    rec = mgr.record("knot-a", exc)
    assert "secret" not in rec.traceback_text
    assert "REDACTED" in rec.traceback_text


def test_exception_manager_no_filter_stores_verbatim() -> None:
    mgr = ExceptionManager(run_id="run-1")
    exc = ValueError("password=hunter2 is wrong")
    rec = mgr.record("knot-a", exc)
    # Without a filter the raw traceback is kept.
    assert "password=hunter2" in rec.traceback_text


# ---------------------------------------------------------------------------
# EmitterErrorPolicy behaviour
# ---------------------------------------------------------------------------


class _BrokenEmitter:
    """An emitter that always raises."""

    @property
    def name(self) -> str:
        return "BrokenEmitter"

    async def on_lineage(self, record: object) -> None:
        raise RuntimeError("boom")

    async def on_run_result(self, result: object) -> None:
        raise RuntimeError("boom")

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_emitter_policy_ignore_swallows_error(caplog: pytest.LogCaptureFixture) -> None:
    """IGNORE policy: no exception escapes, no warning is logged."""
    from pirn.core.knot_factory import knot
    from pirn.tapestry import Tapestry

    @knot
    def source_knot() -> int:
        return 1

    with Tapestry() as t:
        source_knot(_config=KnotConfig(id="source"))

    with caplog.at_level(logging.WARNING, logger="pirn.engine.engine"):
        result = await t.run(
            emitters=[_BrokenEmitter()],
            emitter_error_policy=EmitterErrorPolicy.IGNORE,
        )

    # The run completed; IGNORE means no exception escaped and no warning logged.
    assert result.succeeded
    assert not any("BrokenEmitter" in r.message or "boom" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_emitter_policy_warn_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """WARN policy: warning is logged, run still succeeds."""
    from pirn.core.knot_factory import knot
    from pirn.tapestry import Tapestry

    @knot
    def source_knot() -> int:
        return 1

    with Tapestry() as t:
        source_knot(_config=KnotConfig(id="source"))

    with caplog.at_level(logging.WARNING, logger="pirn.engine.engine"):
        result = await t.run(
            emitters=[_BrokenEmitter()],
            emitter_error_policy=EmitterErrorPolicy.WARN,
        )

    assert result.succeeded
    assert any("BrokenEmitter" in r.message or "boom" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_emitter_policy_raise_propagates_exception() -> None:
    """RAISE policy: the emitter's exception propagates out of run()."""
    from pirn.core.knot_factory import knot
    from pirn.tapestry import Tapestry

    @knot
    def source_knot() -> int:
        return 1

    with Tapestry() as t:
        source_knot(_config=KnotConfig(id="source"))

    with pytest.raises(RuntimeError, match="boom"):
        await t.run(
            emitters=[_BrokenEmitter()],
            emitter_error_policy=EmitterErrorPolicy.RAISE,
        )
