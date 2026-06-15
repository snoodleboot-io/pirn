"""Unit tests for :class:`LineageStore`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn_ml.lineage_store import LineageStore


class _StubLineage(LineageStore):
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._lineages: dict[str, Any] = {}

    async def log_event(self, event_type: str, payload) -> None:
        self._events.append({"type": event_type, "payload": dict(payload)})

    async def fetch_lineage(self, model_id: str):
        return self._lineages.get(model_id, {})

    async def close(self) -> None:
        pass


class TestLineageStoreInterface(unittest.IsolatedAsyncioTestCase):
    async def test_base_log_event_raises(self) -> None:
        store = LineageStore()
        with self.assertRaises(NotImplementedError):
            await store.log_event("train", {})

    async def test_base_fetch_lineage_raises(self) -> None:
        store = LineageStore()
        with self.assertRaises(NotImplementedError):
            await store.fetch_lineage("model-1")

    async def test_base_close_raises(self) -> None:
        store = LineageStore()
        with self.assertRaises(NotImplementedError):
            await store.close()

    def test_clear_credentials_nullifies_config(self) -> None:
        store = LineageStore()
        store._config = {"token": "tok"}  # type: ignore[assignment]
        store._clear_credentials()
        self.assertIsNone(store._config)

    async def test_subclass_log_and_fetch(self) -> None:
        store = _StubLineage()
        await store.log_event("train", {"model_id": "m1"})
        self.assertEqual(len(store._events), 1)
        self.assertEqual(store._events[0]["type"], "train")

    def test_subclass_is_instance_of_lineage_store(self) -> None:
        self.assertIsInstance(_StubLineage(), LineageStore)
