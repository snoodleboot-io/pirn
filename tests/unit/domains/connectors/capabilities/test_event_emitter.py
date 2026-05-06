"""Tests for :class:`EventEmitter`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.capabilities.event_emitter import EventEmitter


class _CountingEmitter(EventEmitter):
    def __init__(self) -> None:
        self._emitted: list = []

    async def emit(self, event) -> None:
        self._emitted.append(event)


class TestEventEmitterInterface(unittest.IsolatedAsyncioTestCase):
    async def test_emit_raises_not_implemented(self) -> None:
        emitter = EventEmitter()
        with self.assertRaises(NotImplementedError):
            await emitter.emit({"event": "test"})

    async def test_emit_many_calls_emit_per_event(self) -> None:
        emitter = _CountingEmitter()
        events = [{"event": "a"}, {"event": "b"}, {"event": "c"}]
        count = await emitter.emit_many(events)
        self.assertEqual(count, 3)
        self.assertEqual(emitter._emitted, events)

    async def test_emit_many_empty(self) -> None:
        emitter = _CountingEmitter()
        count = await emitter.emit_many([])
        self.assertEqual(count, 0)
        self.assertEqual(emitter._emitted, [])
