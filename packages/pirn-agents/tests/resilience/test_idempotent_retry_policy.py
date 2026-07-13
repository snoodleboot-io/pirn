"""Mirrored tests for :class:`IdempotentRetryPolicy` (PIR-506 / S5).

A fake sleep (recording delays, no real time) and a fixed jitter source make
retries deterministic. Verifies safe errors retry with the *same* idempotency
key, unsafe errors fail fast without retrying, the caller key is passed through
to the backend, and the retry budget is honoured.
"""

from __future__ import annotations

import pytest

from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.resilience.idempotency_key_assigner import IdempotencyKeyAssigner
from pirn_agents.resilience.idempotent_retry_policy import IdempotentRetryPolicy
from pirn_agents.resilience.retry_safety_classifier import RetrySafetyClassifier


class _RecordingSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _policy(*, sleep: _RecordingSleep, max_retries: int = 2) -> IdempotentRetryPolicy:
    return IdempotentRetryPolicy(
        backoff=RetryPolicy(max_retries=max_retries, base_delay=0.1, jitter=False),
        sleep=sleep,
    )


class TestConstruction:
    def test_rejects_bad_classifier(self) -> None:
        with pytest.raises(TypeError, match="RetrySafetyClassifier"):
            IdempotentRetryPolicy(classifier=object())  # type: ignore[arg-type]

    def test_rejects_bad_backoff(self) -> None:
        with pytest.raises(TypeError, match="RetryPolicy"):
            IdempotentRetryPolicy(backoff=object())  # type: ignore[arg-type]


class TestSafeRetry:
    async def test_retries_safe_error_then_succeeds(self) -> None:
        sleep = _RecordingSleep()
        keys: list[str] = []
        attempts = {"n": 0}

        async def call(key: str) -> str:
            keys.append(key)
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise TimeoutError("transient")
            return "ok"

        result = await _policy(sleep=sleep).run(operation="charge", arguments={"amt": 5}, call=call)
        assert result == "ok"
        assert attempts["n"] == 3
        assert len(sleep.calls) == 2  # two backoffs before the third success
        # Same idempotency key reused across every attempt.
        assert len(set(keys)) == 1

    async def test_caller_key_passed_through(self) -> None:
        sleep = _RecordingSleep()
        seen: list[str] = []

        async def call(key: str) -> str:
            seen.append(key)
            return "ok"

        await _policy(sleep=sleep).run(
            operation="charge", arguments={"amt": 5}, call=call, caller_key="req-9"
        )
        assert seen == ["req-9"]


class TestUnsafeFailFast:
    async def test_unsafe_error_not_retried(self) -> None:
        sleep = _RecordingSleep()
        attempts = {"n": 0}

        async def call(key: str) -> str:
            attempts["n"] += 1
            raise ValueError("validation")

        with pytest.raises(ValueError, match="validation"):
            await _policy(sleep=sleep).run(operation="charge", arguments={}, call=call)
        assert attempts["n"] == 1  # no retry
        assert sleep.calls == []


class TestBudget:
    async def test_exhausts_retry_budget_and_raises(self) -> None:
        sleep = _RecordingSleep()
        attempts = {"n": 0}

        async def call(key: str) -> str:
            attempts["n"] += 1
            raise TimeoutError("always down")

        with pytest.raises(TimeoutError):
            await _policy(sleep=sleep, max_retries=2).run(
                operation="charge", arguments={}, call=call
            )
        assert attempts["n"] == 3  # initial + 2 retries
        assert sleep.calls == [pytest.approx(0.1), pytest.approx(0.2)]

    async def test_custom_collaborators_compose(self) -> None:
        sleep = _RecordingSleep()
        policy = IdempotentRetryPolicy(
            classifier=RetrySafetyClassifier(safe_exceptions=(KeyError,)),
            assigner=IdempotencyKeyAssigner(namespace="run"),
            backoff=RetryPolicy(max_retries=1, base_delay=0.05, jitter=False),
            sleep=sleep,
        )
        seen: list[str] = []
        attempts = {"n": 0}

        async def call(key: str) -> str:
            seen.append(key)
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise KeyError("transient-by-config")
            return "ok"

        result = await policy.run(operation="charge", arguments={"amt": 5}, call=call)
        assert result == "ok"
        assert attempts["n"] == 2
        assert seen[0].startswith("run:")
        assert len(set(seen)) == 1
