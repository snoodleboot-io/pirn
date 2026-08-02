"""Detect whether calling something produces a coroutine."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


def is_async_callable(candidate: Callable[..., Any]) -> bool:
    """Return True if calling ``candidate`` produces a coroutine.

    ``inspect`` rather than ``asyncio``: ``asyncio.iscoroutinefunction`` is
    deprecated from Python 3.12 and removed in 3.16.

    Neither form sees through a callable *object* whose ``__call__`` carries the
    async, so that case is checked explicitly. Missing it is not cosmetic — a
    node that treats an async combine as sync emits a coroutine object as its
    output instead of the computed value, silently, since a coroutine is a
    perfectly good ``Any``.

    Args:
        candidate: The callable to inspect.

    Returns:
        True if invoking ``candidate`` returns a coroutine.
    """
    if inspect.iscoroutinefunction(candidate):
        return True
    # Fetched statically to inspect it, not to test callability — `callable()`
    # would answer a different question and give nothing to inspect.
    call = inspect.getattr_static(type(candidate), "__call__", None)
    return call is not None and inspect.iscoroutinefunction(call)
