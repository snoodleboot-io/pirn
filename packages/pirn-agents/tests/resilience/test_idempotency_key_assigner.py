"""Mirrored tests for :class:`IdempotencyKeyAssigner` (PIR-506 / S5)."""

from __future__ import annotations

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
