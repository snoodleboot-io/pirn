"""Mirrored tests for :class:`IdempotencyKeyAssigner` (PIR-506 / S5)."""

from __future__ import annotations

import datetime
import decimal
import uuid

import pytest

from pirn_agents.resilience.idempotency_key_assigner import IdempotencyKeyAssigner


class TestCallerKeyPassthrough:
    def test_caller_key_returned_verbatim(self) -> None:
        assigner = IdempotencyKeyAssigner(namespace="tenant")
        key = assigner.assign(operation="charge", arguments={"amt": 5}, caller_key="req-123")
        assert key == "req-123"  # not namespaced, not hashed

    def test_rejects_empty_caller_key(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            IdempotencyKeyAssigner().assign(operation="x", arguments={}, caller_key="")

    def test_rejects_non_string_caller_key(self) -> None:
        with pytest.raises(TypeError, match="caller_key"):
            IdempotencyKeyAssigner().assign(operation="x", arguments={}, caller_key=5)  # type: ignore[arg-type]


class TestDerivation:
    def test_same_call_yields_same_key(self) -> None:
        assigner = IdempotencyKeyAssigner()
        a = assigner.assign(operation="charge", arguments={"amt": 5, "cur": "usd"})
        b = assigner.assign(operation="charge", arguments={"amt": 5, "cur": "usd"})
        assert a == b

    def test_key_is_order_independent(self) -> None:
        assigner = IdempotencyKeyAssigner()
        a = assigner.assign(operation="charge", arguments={"amt": 5, "cur": "usd"})
        b = assigner.assign(operation="charge", arguments={"cur": "usd", "amt": 5})
        assert a == b

    def test_different_args_yield_different_keys(self) -> None:
        assigner = IdempotencyKeyAssigner()
        a = assigner.assign(operation="charge", arguments={"amt": 5})
        b = assigner.assign(operation="charge", arguments={"amt": 6})
        assert a != b

    def test_namespace_prefixes_derived_key(self) -> None:
        assigner = IdempotencyKeyAssigner(namespace="run7")
        key = assigner.assign(operation="charge", arguments={"amt": 5})
        assert key.startswith("run7:")

    def test_rejects_non_mapping_arguments(self) -> None:
        with pytest.raises(TypeError, match="Mapping"):
            IdempotencyKeyAssigner().assign(operation="x", arguments=[1, 2])  # type: ignore[arg-type]


class TestOpaqueArgumentsAreContentKeyed:
    """PIR-795 — the key must be derivable again on the retry it deduplicates."""

    def test_identity_keyed_argument_is_refused_when_the_key_is_issued(self) -> None:
        # The failure this prevents: the argument has no content-derived
        # __repr__, so its rendering embeds a memory address. The retry would
        # derive a DIFFERENT key, defeat the deduplication, and apply the
        # guarded mutation twice. Raising here moves that from a silent
        # double-charge to a loud error at issue time.
        class Cart:
            pass

        with pytest.raises(TypeError, match="memory address"):
            IdempotencyKeyAssigner().assign(operation="charge", arguments={"cart": Cart()})

    def test_a_content_rendering_argument_still_yields_a_stable_key(self) -> None:
        # The other half of the guarantee: narrowing must not reject arguments
        # that already keyed on content, or previously-issued keys would break.
        assigner = IdempotencyKeyAssigner()
        arguments = {
            "at": datetime.datetime(2026, 1, 2, 3, 4, 5),
            "amount": decimal.Decimal("12.34"),
            "request": uuid.UUID(int=7),
        }
        first = assigner.assign(operation="charge", arguments=arguments)
        second = assigner.assign(operation="charge", arguments=dict(arguments))
        assert first == second
        assert len(first) == 64

    def test_the_retry_derives_the_same_key_from_an_equal_argument(self) -> None:
        # An equal-but-distinct instance is what a retry actually reconstructs.
        class Money:
            def __init__(self, cents: int) -> None:
                self.cents = cents

            def __repr__(self) -> str:
                return f"Money({self.cents})"

        assigner = IdempotencyKeyAssigner()
        first = assigner.assign(operation="charge", arguments={"total": Money(500)})
        second = assigner.assign(operation="charge", arguments={"total": Money(500)})
        assert first == second
