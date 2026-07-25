"""Unit tests for :class:`CancellationToken` cooperative-cancellation semantics."""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.performance.cancellation_token import CancellationToken


class TestCancellationToken:
    def test_starts_uncancelled(self) -> None:
        token = CancellationToken()
        assert token.cancelled is False
        assert token.reason is None
        token.raise_if_cancelled()  # no raise

    def test_cancel_sets_flag_and_reason(self) -> None:
        token = CancellationToken()
        token.cancel("budget exhausted")
        assert token.cancelled is True
        assert token.reason == "budget exhausted"

    def test_raise_if_cancelled_raises_cancelled_error(self) -> None:
        token = CancellationToken()
        token.cancel("stop")
        with pytest.raises(asyncio.CancelledError):
            token.raise_if_cancelled()

    def test_cancel_is_idempotent_and_keeps_first_reason(self) -> None:
        token = CancellationToken()
        token.cancel("first")
        token.cancel("second")
        assert token.reason == "first"

    async def test_wait_unblocks_when_cancelled(self) -> None:
        token = CancellationToken()

        async def canceller() -> None:
            token.cancel("go")

        await asyncio.gather(token.wait(), canceller())
        assert token.cancelled is True
