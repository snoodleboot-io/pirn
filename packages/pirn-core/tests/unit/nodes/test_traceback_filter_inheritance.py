"""A traceback filter set once at the top must cover nested runs.

An exception raised inside a `SubTapestry` is recorded twice: by the inner run's
own `ExceptionManager`, and again against the outer knot once the engine
re-registers the placeholder via `RebindableError`.

The outer record was filtered; the inner one was not. That was survivable while
nested runs went unrecorded — and stopped being survivable when PIR-764/765 made
them durable, because a credential in an inner traceback is now persisted to
history verbatim. See PIR-725.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.managers.redact import redact_common_secrets
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

_DSN = "postgresql://admin:hunter2@db.internal/prod"
_KEY = "api_key=sk-live-abc123"


class _Leaky(Source):
    async def process(self, **_: Any) -> Any:
        raise RuntimeError(f"connect failed: {_DSN} {_KEY}")


class _Pipeline(SubTapestry):
    async def process(self, **_: Any) -> Knot:
        return _Leaky(_config=KnotConfig(id="leaky"))


def _leaks(text: str) -> bool:
    return "hunter2" in text or "sk-live-abc123" in text


class TestTracebackFilterReachesNestedRuns(unittest.IsolatedAsyncioTestCase):
    async def _run(self) -> tuple[Any, InMemoryHistory]:
        history = InMemoryHistory()
        with Tapestry(history=history, traceback_filter=redact_common_secrets) as t:
            _Pipeline(_config=KnotConfig(id="pipe"))
        result = await t.run(RunRequest())
        self.assertFalse(result.succeeded)
        return result, history

    async def test_the_outer_record_is_redacted(self) -> None:
        """Already true before PIR-725 — pinned so a regression is attributable."""
        result, _ = await self._run()
        self.assertTrue(result.exceptions)
        for record in result.exceptions:
            self.assertFalse(_leaks(record.traceback_text), record.knot_id)

    async def test_the_inner_run_record_is_redacted(self) -> None:
        """The leak PIR-725 closes."""
        result, history = await self._run()
        inner_records = []
        for child in await history.children_of(result.run_id):
            inner = await history.get_run(child.run_id)
            if inner is not None:
                inner_records.extend(inner.exceptions)

        self.assertTrue(inner_records, "no inner run recorded — the test is vacuous")
        for record in inner_records:
            self.assertFalse(_leaks(record.traceback_text), record.knot_id)

    async def test_the_filter_actually_ran_rather_than_the_secret_being_absent(self) -> None:
        """Guard against passing because nothing was captured at all.

        `assertFalse(_leaks(...))` is satisfied by an empty string, so without
        this the two tests above would still pass if inner tracebacks stopped
        being recorded entirely.
        """
        result, history = await self._run()
        texts: list[str] = []
        for child in await history.children_of(result.run_id):
            inner = await history.get_run(child.run_id)
            if inner is not None:
                texts.extend(e.traceback_text for e in inner.exceptions)

        self.assertTrue(texts, "no inner traceback captured")
        self.assertTrue(any("<redacted>" in t for t in texts), texts)
        self.assertTrue(any("connect failed" in t for t in texts), "traceback body lost")
