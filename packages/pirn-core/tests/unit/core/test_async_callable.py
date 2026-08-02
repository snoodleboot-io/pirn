"""Unit tests for is_async_callable."""

from __future__ import annotations

import unittest
from functools import partial

from pirn.core.async_callable import is_async_callable


class TestIsAsyncCallable(unittest.TestCase):
    def test_async_function(self) -> None:
        async def fn() -> None: ...

        assert is_async_callable(fn) is True

    def test_sync_function(self) -> None:
        def fn() -> None: ...

        assert is_async_callable(fn) is False

    def test_builtin(self) -> None:
        assert is_async_callable(sum) is False

    def test_object_with_async_dunder_call(self) -> None:
        """The case neither asyncio nor bare inspect detects."""

        class _AsyncCallable:
            async def __call__(self) -> None: ...

        assert is_async_callable(_AsyncCallable()) is True

    def test_object_with_sync_dunder_call(self) -> None:
        class _SyncCallable:
            def __call__(self) -> None: ...

        assert is_async_callable(_SyncCallable()) is False

    def test_partial_of_async_function(self) -> None:
        async def fn(x: int) -> int:
            return x

        assert is_async_callable(partial(fn, 1)) is True
