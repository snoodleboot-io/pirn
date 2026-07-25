"""``IdempotentRetryPolicy`` — retry only safe calls, reusing one key.

Ties the three S5 pieces together: it assigns a stable idempotency key once via
an :class:`~pirn_agents.resilience.idempotency_key_assigner.IdempotencyKeyAssigner`,
invokes the call passing that key through, and on failure consults a
:class:`~pirn_agents.resilience.retry_safety_classifier.RetrySafetyClassifier`.
An unsafe classification (validation / 4xx / unknown) re-raises immediately — a
mutating call is never blindly retried — while a safe one backs off (reusing the
F3 :class:`~pirn_agents.llm.retry_policy.RetryPolicy` shape) and retries with the
*same* idempotency key, so the backend can dedupe the repeated mutation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.resilience.idempotency_key_assigner import IdempotencyKeyAssigner
from pirn_agents.resilience.retry_classification import RetryClassification
from pirn_agents.resilience.retry_safety_classifier import RetrySafetyClassifier


class IdempotentRetryPolicy:
    """Run a mutating call with safe-retry classification and a stable key."""

    def __init__(
        self,
        *,
        classifier: RetrySafetyClassifier | None = None,
        assigner: IdempotencyKeyAssigner | None = None,
        backoff: RetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Assemble the policy from its collaborators.

        Args:
            classifier: Safe/unsafe error classifier; defaults to a stock
                :class:`RetrySafetyClassifier`.
            assigner: Idempotency-key assigner; defaults to a stock
                :class:`IdempotencyKeyAssigner`.
            backoff: Backoff shape (attempt budget + delays); defaults to a stock
                :class:`RetryPolicy`.
            sleep: Async sleep used between retries; defaults to
                :func:`asyncio.sleep`. Injected in tests.

        Raises:
            TypeError: If any supplied collaborator is of the wrong type.
        """
        self._classifier = classifier if classifier is not None else RetrySafetyClassifier()
        self._assigner = assigner if assigner is not None else IdempotencyKeyAssigner()
        self._backoff = backoff if backoff is not None else RetryPolicy()
        self._sleep = sleep if sleep is not None else asyncio.sleep
        if not isinstance(self._classifier, RetrySafetyClassifier):
            raise TypeError(
                f"IdempotentRetryPolicy: classifier must be a RetrySafetyClassifier, "
                f"got {type(self._classifier).__name__}"
            )
        if not isinstance(self._assigner, IdempotencyKeyAssigner):
            raise TypeError(
                f"IdempotentRetryPolicy: assigner must be an IdempotencyKeyAssigner, "
                f"got {type(self._assigner).__name__}"
            )
        if not isinstance(self._backoff, RetryPolicy):
            raise TypeError(
                f"IdempotentRetryPolicy: backoff must be a RetryPolicy, "
                f"got {type(self._backoff).__name__}"
            )

    async def run(
        self,
        *,
        operation: str,
        arguments: Mapping[str, Any],
        call: Callable[[str], Awaitable[Any]],
        caller_key: str | None = None,
        rng: Callable[[], float] | None = None,
    ) -> Any:
        """Execute ``call`` with safe-retry semantics and a stable key.

        The idempotency key is assigned once and passed to every attempt, so a
        retried mutation carries the same key the backend can dedupe on.

        Args:
            operation: Stable operation name (used to derive a key if needed).
            arguments: Call arguments (canonicalised for a derived key).
            call: Async callable receiving the idempotency key and performing
                the mutating call.
            caller_key: Optional caller-stable idempotency key.
            rng: Optional jitter source forwarded to the backoff, for
                deterministic delays in tests.

        Returns:
            The successful return value of ``call``.

        Raises:
            BaseException: The last exception, re-raised when it is classified
                unsafe or the retry budget is exhausted.
        """
        key = self._assigner.assign(operation=operation, arguments=arguments, caller_key=caller_key)
        attempt = 0
        while True:
            try:
                return await call(key)
            except Exception as exc:
                unsafe = self._classifier.classify(exc) is RetryClassification.UNSAFE
                if unsafe or attempt >= self._backoff.max_retries:
                    raise
                await self._sleep(self._backoff.backoff_delay(attempt, rng=rng))
                attempt += 1
