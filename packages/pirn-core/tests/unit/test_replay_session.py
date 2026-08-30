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
from pirn.exceptions.data_integrity_error import DataIntegrityError
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
    config_values_hash: str | None = None,
    error_record_id: str | None = None,
    skip_reason: str | None = None,
) -> KnotLineage:
    return KnotLineage(
        run_id="run-source",
        knot_id=knot_id,
        knot_class="tests.Leaf",
        knot_config_hash=config_hash,
        config_values_hash=config_values_hash,
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


async def test_resolve_reports_an_evicted_value_as_unavailable() -> None:
    # Arrange — the value was written, then dropped when the store hit its
    # declared ceiling.  The lineage row is untouched and still names it.
    knot = Leaf(_config=KnotConfig(id="leaf"))
    config_hash = content_hash(knot.config.model_dump(mode="json"))
    recorded = content_hash(1234)
    data_store = InMemoryDataStore(max_values=1)
    await data_store.put(recorded, 1234)
    await data_store.put(content_hash("something else"), "something else")
    session = ReplaySession(
        source_run=_run([_row(knot_id="leaf", output_hash=recorded, config_hash=config_hash)])
    )

    # Act / Assert — never a wrong answer, and never a re-execution.
    with pytest.raises(ReplayValueUnavailableError) as caught:
        await session.resolve(
            knot=knot,
            knot_config_hash=config_hash,
            parent_input_hashes={},
            data_store=data_store,
        )
    assert caught.value.output_hash == recorded
    assert "evicted" in str(caught.value)


async def test_resolve_does_not_leak_a_bare_key_error_from_the_store() -> None:
    # Arrange — a store that evicts between `has()` and `get()` used to leak a
    # KeyError past this method's documented contract.  Reading once closes
    # the window; this pins the resulting type.
    knot = Leaf(_config=KnotConfig(id="leaf"))
    config_hash = content_hash(knot.config.model_dump(mode="json"))
    recorded = content_hash(1234)

    class _VanishingStore(InMemoryDataStore):
        async def has(self, content_hash: str) -> bool:
            return True

    session = ReplaySession(
        source_run=_run([_row(knot_id="leaf", output_hash=recorded, config_hash=config_hash)])
    )

    # Act / Assert
    with pytest.raises(ReplayValueUnavailableError):
        await session.resolve(
            knot=knot,
            knot_config_hash=config_hash,
            parent_input_hashes={},
            data_store=_VanishingStore(),
        )


async def test_resolve_does_not_launder_an_integrity_failure_into_a_missing_value() -> None:
    # Arrange — a store whose bytes failed their signature check is a
    # different failure and must surface as itself.
    knot = Leaf(_config=KnotConfig(id="leaf"))
    config_hash = content_hash(knot.config.model_dump(mode="json"))
    recorded = content_hash(1234)

    class _TamperedStore(InMemoryDataStore):
        async def get(self, content_hash: str) -> Any:
            raise DataIntegrityError("signature mismatch")

    session = ReplaySession(
        source_run=_run([_row(knot_id="leaf", output_hash=recorded, config_hash=config_hash)])
    )

    # Act / Assert
    with pytest.raises(DataIntegrityError):
        await session.resolve(
            knot=knot,
            knot_config_hash=config_hash,
            parent_input_hashes={},
            data_store=_TamperedStore(),
        )


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


# ---------------------------------------------------------------- PIR-836


class WithOpaqueLiteral(Knot):
    """A knot whose literal argument has no canonical content hash.

    A bare object declares no pydantic schema and no ``__pirn_canonical__``, so
    ``content_hash`` cannot canonicalise it and emits an ``unhashable`` marker
    naming only the type — a value every instance of that type shares.
    """

    def __init__(self, resource: Any, **kwargs: Any) -> None:
        super().__init__(resource=resource, **kwargs)

    async def process(self, resource: Any, **_: Any) -> int:
        return 1


class _BareResource:
    """No pydantic schema, no canonical hook — deliberately opaque."""


def test_uncomparable_literals_are_not_mistaken_for_a_match() -> None:
    """Two *different* opaque literals hash alike, so equality proves nothing.

    This is the failure mode that makes ``is_comparable`` necessary: an
    identity-keyed ``PirnOpaqueValue`` produces a false *mismatch* (safe —
    replay refuses), but a fully opaque object collapses to
    ``sha256:unhashable:<Type>`` and produces a false *match*, which would
    serve a recorded output for a knot configured with a different object.
    """
    # Arrange
    one = WithOpaqueLiteral(resource=_BareResource(), _config=KnotConfig(id="r"))
    other = WithOpaqueLiteral(resource=_BareResource(), _config=KnotConfig(id="r"))

    # Act
    hash_one = InvocationIdentity.config_values_hash(one)
    hash_other = InvocationIdentity.config_values_hash(other)

    # Assert — equal despite describing different objects, hence uncomparable.
    assert hash_one == hash_other
    assert not InvocationIdentity.is_comparable(hash_one)


def test_hashable_literals_are_comparable() -> None:
    # Arrange
    knot = WithLiterals(factor=2, _config=KnotConfig(id="scale"))

    # Act
    digest = InvocationIdentity.config_values_hash(knot)

    # Assert
    assert InvocationIdentity.is_comparable(digest)


def test_absent_literals_are_comparable() -> None:
    # Two knots that both have no literals genuinely agree.
    assert InvocationIdentity.is_comparable(None)


async def test_replay_refuses_a_knot_whose_literals_cannot_be_compared() -> None:
    """Fail loud rather than serve a value the recording cannot vouch for."""
    # Arrange — the recorded row agrees with this run on every hash, including
    # the uncomparable one, so the equality check alone would let it through.
    knot = WithOpaqueLiteral(resource=_BareResource(), _config=KnotConfig(id="r"))
    recorded = InvocationIdentity.config_values_hash(knot)
    session = ReplaySession(
        source_run=_run([_row(knot_id="r", output_hash=None, config_values_hash=recorded)])
    )

    # Act / Assert
    with pytest.raises(ReplayMismatchError, match="no canonical content hash"):
        await session.resolve(
            knot=knot,
            knot_config_hash="sha256:cfg",
            parent_input_hashes={},
            data_store=InMemoryDataStore(),
        )
