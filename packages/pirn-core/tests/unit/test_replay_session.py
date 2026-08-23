"""Unit tests for ``ReplaySession`` and ``InvocationIdentity``.

These exercise the matching rules directly, without an engine, so a failure
points at the rule rather than at the run that tripped it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.core.err import Err
from pirn.core.hashing import content_hash
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.lineage import KnotLineage
from pirn.core.ok import Ok
from pirn.core.run_result import RunResult
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord
from pirn.recording.invocation_identity import InvocationIdentity
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_session import ReplaySession
from pirn.recording.replay_value_unavailable_error import ReplayValueUnavailableError


class Leaf(Knot):
    """A parentless knot with no literal inputs."""

    async def process(self, **_: Any) -> int:
        return 1


class WithLiterals(Knot):
    """A knot carrying a literal constructor argument."""

    def __init__(self, factor: int, **kwargs: Any) -> None:
        super().__init__(factor=factor, **kwargs)

    async def process(self, factor: int, **_: Any) -> int:
        return factor


def _row(
    *,
    knot_id: str,
    outcome: str = "ok",
    output_hash: str | None = None,
    config_hash: str = "sha256:cfg",
    parent_input_hashes: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
    error_record_id: str | None = None,
    skip_reason: str | None = None,
) -> KnotLineage:
    return KnotLineage(
        run_id="run-source",
        knot_id=knot_id,
        knot_class="tests.Leaf",
        knot_config_hash=config_hash,
        parent_input_hashes=parent_input_hashes or {},
        output_hash=output_hash,
        outcome=outcome,
        error_record_id=error_record_id,
        skip_reason=skip_reason,
        dispatcher="LocalDispatcher",
        extra=extra or {},
    )


def _run(
    rows: list[KnotLineage],
    exceptions: list[ExceptionRecord] | None = None,
) -> RunResult:
    now = datetime.now(UTC)
    return RunResult(
        run_id="run-source",
        terminals_requested=[row.knot_id for row in rows],
        outputs={},
        lineage=rows,
        exceptions=exceptions or [],
        started_at=now,
        finished_at=now,
        dispatcher="LocalDispatcher",
    )


def test_config_values_hash_is_none_without_literal_inputs() -> None:
    # Arrange / Act
    knot = Leaf(_config=KnotConfig(id="leaf"))

    # Assert
    assert InvocationIdentity.config_values_hash(knot) is None


def test_config_values_hash_separates_knots_that_lineage_cannot() -> None:
    # Arrange — these two agree on knot_config_hash and parent_input_hashes.
    two = WithLiterals(factor=2, _config=KnotConfig(id="scale"))
    five = WithLiterals(factor=5, _config=KnotConfig(id="scale"))

    # Act
    hash_two = InvocationIdentity.config_values_hash(two)
    hash_five = InvocationIdentity.config_values_hash(five)

    # Assert
    assert two.config.model_dump(mode="json") == five.config.model_dump(mode="json")
    assert hash_two is not None
    assert hash_two != hash_five


async def test_resolve_serves_the_recorded_value() -> None:
    # Arrange
    store = InMemoryDataStore()
    value_hash = content_hash(99)
    await store.put(value_hash, 99)
    knot = Leaf(_config=KnotConfig(id="leaf"))
    config_hash = content_hash(knot.config.model_dump(mode="json"))
    session = ReplaySession(
        source_run=_run([_row(knot_id="leaf", output_hash=value_hash, config_hash=config_hash)])
    )

    # Act
    result = await session.resolve(
        knot=knot,
        knot_config_hash=config_hash,
        parent_input_hashes={},
        data_store=store,
    )

    # Assert
    assert isinstance(result, Ok)
    assert result.value == 99


async def test_resolve_replays_a_skip_with_its_recorded_reason() -> None:
    # Arrange
    knot = Leaf(_config=KnotConfig(id="leaf"))
    config_hash = content_hash(knot.config.model_dump(mode="json"))
    session = ReplaySession(
        source_run=_run(
            [
                _row(
                    knot_id="leaf",
                    outcome="skipped",
                    skip_reason="gate_closed",
                    config_hash=config_hash,
                )
            ]
        )
    )

    # Act
    result = await session.resolve(
        knot=knot,
        knot_config_hash=config_hash,
        parent_input_hashes={},
        data_store=InMemoryDataStore(),
    )

    # Assert
    assert isinstance(result, Skipped)
    assert result.reason == "gate_closed"


async def test_resolve_replays_a_failure_from_the_recorded_exception() -> None:
    # Arrange
    knot = Leaf(_config=KnotConfig(id="leaf"))
    config_hash = content_hash(knot.config.model_dump(mode="json"))
    recorded = ExceptionRecord(
        run_id="run-source",
        knot_id="leaf",
        exc_type="TimeoutError",
        message="upstream timed out",
        traceback_text="…",
    )
    session = ReplaySession(
        source_run=_run(
            [
                _row(
                    knot_id="leaf",
                    outcome="err",
                    error_record_id=recorded.id,
                    config_hash=config_hash,
                )
            ],
            exceptions=[recorded],
        )
    )

    # Act
    result = await session.resolve(
        knot=knot,
        knot_config_hash=config_hash,
        parent_input_hashes={},
        data_store=InMemoryDataStore(),
    )

    # Assert — an unbound placeholder the engine will re-register.
    assert isinstance(result, Err)
    assert result.record.exc_type == "TimeoutError"
    assert result.record.message == "upstream timed out"
    assert result.record.run_id == "<unbound>"


async def test_resolve_rejects_changed_parent_input_hashes() -> None:
    # Arrange
    knot = Leaf(_config=KnotConfig(id="leaf"))
    config_hash = content_hash(knot.config.model_dump(mode="json"))
    session = ReplaySession(
        source_run=_run(
            [
                _row(
                    knot_id="leaf",
                    output_hash=content_hash(1),
                    config_hash=config_hash,
                    parent_input_hashes={"x": "sha256:recorded"},
                )
            ]
        )
    )

    # Act / Assert
    with pytest.raises(ReplayMismatchError) as caught:
        await session.resolve(
            knot=knot,
            knot_config_hash=config_hash,
            parent_input_hashes={"x": "sha256:different"},
            data_store=InMemoryDataStore(),
        )
    assert "parent input hashes differ" in caught.value.reason


async def test_resolve_rejects_a_changed_knot_config() -> None:
    # Arrange
    knot = Leaf(_config=KnotConfig(id="leaf"))
    session = ReplaySession(
        source_run=_run(
            [_row(knot_id="leaf", output_hash=content_hash(1), config_hash="sha256:old")]
        )
    )

    # Act / Assert
    with pytest.raises(ReplayMismatchError) as caught:
        await session.resolve(
            knot=knot,
            knot_config_hash="sha256:new",
            parent_input_hashes={},
            data_store=InMemoryDataStore(),
        )
    assert "knot config hash changed" in caught.value.reason


async def test_resolve_reports_a_missing_value_separately_from_a_mismatch() -> None:
    # Arrange — the row is a perfect match; only the value is gone.
    knot = Leaf(_config=KnotConfig(id="leaf"))
    config_hash = content_hash(knot.config.model_dump(mode="json"))
    absent = content_hash(1234)
    session = ReplaySession(
        source_run=_run([_row(knot_id="leaf", output_hash=absent, config_hash=config_hash)])
    )

    # Act / Assert
    with pytest.raises(ReplayValueUnavailableError) as caught:
        await session.resolve(
            knot=knot,
            knot_config_hash=config_hash,
            parent_input_hashes={},
            data_store=InMemoryDataStore(),
        )
    assert caught.value.output_hash == absent


def test_verify_executed_accepts_a_matching_output_hash() -> None:
    # Arrange
    session = ReplaySession(source_run=_run([_row(knot_id="param:x", output_hash="sha256:v")]))

    # Act / Assert — no raise.
    session.verify_executed(knot_id="param:x", output_hash="sha256:v")


def test_verify_executed_rejects_a_different_output_hash() -> None:
    # Arrange
    session = ReplaySession(source_run=_run([_row(knot_id="param:x", output_hash="sha256:v")]))

    # Act / Assert
    with pytest.raises(ReplayMismatchError) as caught:
        session.verify_executed(knot_id="param:x", output_hash="sha256:other")
    assert caught.value.source_run_id == "run-source"


def test_row_for_returns_none_for_an_unrecorded_knot() -> None:
    # Arrange
    session = ReplaySession(source_run=_run([_row(knot_id="leaf", output_hash="sha256:v")]))

    # Act / Assert
    assert session.row_for("leaf") is not None
    assert session.row_for("absent") is None
