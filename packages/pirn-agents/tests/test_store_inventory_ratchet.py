"""Guard: there is one key→value plane, and it is core's ``DataStore``.

ADR "agents speaks core" WS3 moves memory, sessions and determinism onto core's
value and lineage planes. A class that keeps its own ``dict`` and offers put/get
over it is a second value plane: nothing a run replays, records lineage for,
resolves identities against, or shares between the knots that need the same
value.

There is no design inventory here. The version this replaced named nine keyed
stores with a one-line reason each and froze the set by exact equality — and its
detector, which matched three hard-coded method-name pairs, could not see the
``register``/``get`` stores that existed the whole time, so the inventory it
froze was not the inventory of stores. The assertion below is the rule itself:
**no class holds a keyed store of its own**. :class:`TestKeyedStoreDetectorFires`
proves the detector fires, so an empty finding means an empty tree and not a
blind detector.
"""

from __future__ import annotations

import ast
import unittest

from tests.agents_source_index import AgentsSourceIndex
from tests.source_shapes import SourceShapes
from tests.store_inventory import StoreInventory


class TestThereIsOneValuePlane(unittest.TestCase):
    """No class holds a keyed store of its own. Asserted, not inventoried."""

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that scans nothing passes for the wrong reason."""
        assert len(AgentsSourceIndex.classes()) >= 500, len(AgentsSourceIndex.classes())

    def test_no_class_holds_a_keyed_store_of_its_own(self) -> None:
        found = StoreInventory.discover()
        assert found == {}, {label: sorted(stores) for label, stores in found.items()}


class TestKeyedStoreDetectorFires(unittest.TestCase):
    """The detector fires on the shape it names, and not on a delegating adapter."""

    @staticmethod
    def _stores(source: str) -> frozenset[str]:
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef))
        return SourceShapes.keyed_store_attributes(node)

    def test_rule_fires_on_a_put_get_store(self) -> None:
        assert self._stores(
            "class Cache:\n"
            "    def put(self, key, value):\n"
            "        self._values[key] = value\n"
            "    def get(self, key):\n"
            "        return self._values.get(key)\n"
        ) == frozenset({"_values"})

    def test_rule_fires_on_a_register_get_store(self) -> None:
        """The shape the name-keyed version could not see at all."""
        assert self._stores(
            "class ToolRegistry:\n"
            "    def register(self, namespace, factory):\n"
            "        key = (namespace, factory.name)\n"
            "        self._by_key[key] = factory\n"
            "    def lookup(self, namespace, name):\n"
            "        return self._by_key.get((namespace, name))\n"
        ) == frozenset({"_by_key"})

    def test_rule_fires_on_a_store_spelled_with_no_familiar_verb_at_all(self) -> None:
        assert self._stores(
            "class Slab:\n"
            "    def remember(self, token, blob):\n"
            "        self._slab[token] = blob\n"
            "    def recall(self, token):\n"
            "        return self._slab[token]\n"
        ) == frozenset({"_slab"})

    def test_rule_names_every_store_a_class_holds(self) -> None:
        assert self._stores(
            "class Twin:\n"
            "    def put(self, key, value, tags):\n"
            "        self._values[key] = value\n"
            "        self._tags[key] = tags\n"
            "    def get(self, key):\n"
            "        return self._values[key], self._tags[key]\n"
        ) == frozenset({"_values", "_tags"})

    def test_rule_ignores_an_adapter_that_delegates_to_a_data_store(self) -> None:
        assert (
            self._stores(
                "class DataStoreMemoryStore:\n"
                "    async def store(self, key, value):\n"
                "        await self._data_store.put(key, value)\n"
                "    async def retrieve(self, key):\n"
                "        return await self._data_store.get(key)\n"
            )
            == frozenset()
        )

    def test_rule_ignores_a_write_only_accumulator(self) -> None:
        """Collecting is not storing; reading back under a key is."""
        assert (
            self._stores(
                "class Collector:\n"
                "    def add(self, key, value):\n"
                "        self._seen[key] = value\n"
                "    def all(self):\n"
                "        return dict(self._seen)\n"
            )
            == frozenset()
        )

    def test_rule_ignores_a_fixed_slot_read_under_a_literal(self) -> None:
        """A constant index into own state is a field, not a key."""
        assert (
            self._stores(
                "class Pair:\n"
                "    def set_head(self, value):\n"
                "        self._slots[0] = value\n"
                "    def head(self):\n"
                "        return self._slots[0]\n"
            )
            == frozenset()
        )

    def test_rule_ignores_a_class_with_no_state_of_its_own(self) -> None:
        assert (
            self._stores("class Plain:\n    def run(self, value):\n        return value\n")
            == frozenset()
        )
