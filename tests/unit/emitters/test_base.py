"""Unit tests for Emitter base class."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.emitters.base import Emitter


class TestEmitterBase(unittest.IsolatedAsyncioTestCase):
    def test_name_returns_class_name(self) -> None:
        e = Emitter()
        self.assertEqual(e.name, "Emitter")

    def test_subclass_name(self) -> None:
        class MyEmitter(Emitter):
            pass

        self.assertEqual(MyEmitter().name, "MyEmitter")

    async def test_on_status_is_noop(self) -> None:
        e = Emitter()
        event = MagicMock()
        await e.on_status(event)  # no exception

    async def test_on_lineage_is_noop(self) -> None:
        e = Emitter()
        record = MagicMock()
        await e.on_lineage(record)

    async def test_on_run_result_is_noop(self) -> None:
        e = Emitter()
        result = MagicMock()
        await e.on_run_result(result)

    async def test_close_is_noop(self) -> None:
        e = Emitter()
        await e.close()
