"""Ratchet: freeze the keyed-store and session/determinism-lifecycle inventory.

ADR "agents speaks core" WS3 (memory, sessions, determinism onto core's value
and lineage planes; see ``.prompticorn/sessions/agents-realignment-proposal-
20260913.md``) burns this inventory down as writer/recall knots move onto
``Payload`` + ``DataStore``/``RunHistory`` and sessions/determinism move onto
``RunResult``/``ReplaySession``. Two independent counts, in the style of
``tests/specializations/base/test_no_engine_bypass.py``:

* every class in ``pirn_agents`` whose method surface is a keyed store
  (``store``/``retrieve``/``forget``, ``put``/``get``, ``save``/``load``, or a
  namespaced ``search``) — a *fourth* ad hoc keyed store appearing here
  without shrinking an existing one is exactly the growth WS3 exists to stop;
* every module importing ``RunCheckpoint`` or a ``*Cassette*`` name — the
  session/determinism value shapes replaced by ``RunResult``/``ReplaySession``.

PIR-872 turned the first into a named design inventory (every keyed store with
the reason it is not a shadow of core) and burned the second to empty. Both are
asserted by **exact equality**: a new entry fails because it is not named
(growth caught); removing/renaming a store without updating the inventory also
fails, because the inventory still names it.
"""

from __future__ import annotations

import ast
import unittest

from tests.store_inventory import StoreInventory

# --- keyed-store design inventory --------------------------------------------
# Every class with a keyed-store method surface, each named with the reason it
# is not a shadow of core's ``DataStore``/``RunHistory``. PIR-872 collapsed the
# shadows: ``ResultCache``/``InMemoryResultCache``/``SemanticResultCache`` no
# longer re-expose ``get``/``put``/``has`` over their ``DataStore`` (raw keyed
# access is ``cache.store``), and ``VectorMemoIndex`` -- a private key->vector
# dict beside ``DataStore`` -- is deleted (``EmbeddingCache`` stores vectors in
# an ``InMemoryDataStore``). What remains is design, not drift: an agents-layer
# similarity-memory seam core has no equivalent of, its adapters to external
# systems, and the keyed-identity adapter onto core's own lineage plane. A new
# keyed store fails here until it is justified the same way. Regenerate the
# keys with StoreInventory.discover_store_classes() from packages/pirn-agents.

KEYED_STORE_DESIGN_INVENTORY: dict[str, str] = {
    "connectors/streaming_s3_store.py::StreamingS3Store": (
        "external-system adapter: core S3Store subclass adding a multipart streaming put"
    ),
    "memory/stores/data_store_memory_store.py::DataStoreMemoryStore": (
        "MemoryStore backend whose values are core DataStore/RunHistory rows via KeyedLineageStore"
    ),
    "memory/stores/keyed_lineage_store.py::KeyedLineageStore": (
        "adapter onto core's lineage plane: a caller key is a knot id, values in DataStore"
    ),
    "memory/stores/memory_store.py::MemoryStore": (
        "agents-layer similarity-memory seam (keyed recall + vector search); core has no search"
    ),
    "retrieval/vector_stores/chroma_memory_store.py::ChromaMemoryStore": (
        "external-system adapter: Chroma vector database client"
    ),
    "retrieval/vector_stores/in_memory_vector_store.py::InMemoryVectorStore": (
        "in-process reference backend of the vector seam (nearest-neighbour search, no service)"
    ),
    "retrieval/vector_stores/pgvector_memory_store.py::PgvectorMemoryStore": (
        "external-system adapter: Postgres pgvector client"
    ),
    "retrieval/vector_stores/qdrant_memory_store.py::QdrantMemoryStore": (
        "external-system adapter: Qdrant vector database client"
    ),
    "retrieval/vector_stores/vector_memory_store.py::VectorMemoryStore": (
        "vector-native base (upsert/query) shared by the vector database adapters"
    ),
}

# --- known RunCheckpoint/Cassette* importers ----------------------------------
# Regenerate by running StoreInventory.discover_lifecycle_importers() from the
# package root and pasting the sorted keys below.

# ADR agents-speaks-core WS3 part 2 lowered this from 11 to 9 (the rewritten
# sessions/approval_resumer.py and sessions/suspending_approval_check.py no
# longer import RunState/RunCheckpoint at all — a suspend is now
# Skipped(reason="awaiting_human"), and resume replays from RunHistory via
# ReplaySession — see pirn_agents.sessions.session_chain). Part 3 lowered it
# again, 9 to 7: determinism/checkpoint_forker.py and fork_result.py no
# longer import RunState/RunCheckpoint either — a fork is now a branch of the
# run chain (ResumeToken-shaped fork point + ReplaySession(allow_new_knots=
# True)), not a RunCheckpoint rewind. PIR-864 deleted the remaining five
# one-cycle shims this list named (sessions/* and batch/batch_checkpointer.py),
# leaving two real, non-deprecated importers; PIR-872 deleted
# batch/batch_progress.py's to_run_state()/from_run_state() bridge (a per-fire
# summary checkpoints nothing), leaving sessions/run_resumer.py.
# PIR-872 emptied this. batch/batch_progress.py's RunState bridge is deleted
# (a per-fire summary checkpoints nothing). RunState itself is no longer a
# lifecycle checkpoint value: since ADR WS3 part 2 it is a read model projected
# from a session's RunHistory chain (RunState.from_chain) and never persisted,
# so sessions/run_resumer.py -- which projects it from RunHistory -- is reading
# core's lineage plane, not a parallel one; StoreInventory no longer counts the
# name. RunCheckpoint and any Cassette* name still trip. Empty, not deleted.
LIFECYCLE_IMPORTERS: frozenset[str] = frozenset()


class TestStoreInventoryIsFrozen(unittest.TestCase):
    """Freeze the keyed-store and lifecycle-importer inventories. Exact equality."""

    def test_the_store_walk_is_not_vacuous(self) -> None:
        """A guard that finds nothing passes for the wrong reason."""
        found = StoreInventory.discover_store_classes()
        assert len(found) >= 5, len(found)

    def test_the_importer_walk_is_not_vacuous(self) -> None:
        # Every importer is gone (LIFECYCLE_IMPORTERS above), so vacuity is
        # checked on the scanner: it must still read real import syntax.
        matched = StoreInventory._lifecycle_imports(
            "from pirn_agents.sessions.run_checkpoint import RunCheckpoint\n"
        )
        assert matched == ("RunCheckpoint",)

    def test_keyed_store_classes_match_the_design_inventory(self) -> None:
        found = frozenset(StoreInventory.discover_store_classes())
        named = frozenset(KEYED_STORE_DESIGN_INVENTORY)
        assert found == named, {
            "unjustified keyed stores": sorted(found - named),
            "gone — remove from KEYED_STORE_DESIGN_INVENTORY": sorted(named - found),
        }

    def test_every_inventory_entry_names_its_reason(self) -> None:
        for label, reason in KEYED_STORE_DESIGN_INVENTORY.items():
            assert reason.strip(), label

    def test_the_collapsed_shadows_stay_collapsed(self) -> None:
        found = frozenset(StoreInventory.discover_store_classes())
        for label in (
            "caching/in_memory_result_cache.py::InMemoryResultCache",
            "caching/result_cache.py::ResultCache",
            "caching/semantic_result_cache.py::SemanticResultCache",
            "caching/vector_memo_index.py::VectorMemoIndex",
        ):
            assert label not in found, label

    def test_lifecycle_importers_are_frozen(self) -> None:
        found = frozenset(StoreInventory.discover_lifecycle_importers())
        assert found == LIFECYCLE_IMPORTERS, {
            "new importers": sorted(found - LIFECYCLE_IMPORTERS),
            "shrunk — remove from LIFECYCLE_IMPORTERS": sorted(LIFECYCLE_IMPORTERS - found),
        }


class TestDetectorsAreDiscriminating(unittest.TestCase):
    """The detectors must fire on the shapes they name, and not on clean code.

    Without these, an allowlist that matches a detector which silently
    stopped working would still be green — the failure mode a ratchet is
    most prone to.
    """

    # -- is_keyed_store ------------------------------------------------------

    def test_store_retrieve_pair_trips(self) -> None:
        class _S:
            def store(self) -> None: ...
            def retrieve(self) -> None: ...

        assert StoreInventory.is_keyed_store(_S)

    def test_put_get_pair_trips(self) -> None:
        class _S:
            def put(self) -> None: ...
            def get(self) -> None: ...

        assert StoreInventory.is_keyed_store(_S)

    def test_save_load_pair_trips(self) -> None:
        class _S:
            def save(self) -> None: ...
            def load(self) -> None: ...

        assert StoreInventory.is_keyed_store(_S)

    def test_namespaced_search_trips(self) -> None:
        class _S:
            def search(self) -> None: ...
            def store(self) -> None: ...

        assert StoreInventory.is_keyed_store(_S)

    def test_inherited_accessors_still_trip(self) -> None:
        class _Base:
            def store(self) -> None: ...
            def retrieve(self) -> None: ...

        class _Child(_Base):
            """Inherits the pair unchanged; still a keyed store."""

        assert StoreInventory.is_keyed_store(_Child)

    def test_bare_search_does_not_trip(self) -> None:
        """A similarity search with no keyed accessor next to it is not a store."""

        class _Searcher:
            def search(self) -> None: ...

        assert not StoreInventory.is_keyed_store(_Searcher)

    def test_unrelated_get_put_names_alone_do_not_trip_without_pair(self) -> None:
        """Only ``get`` with no ``put`` (e.g. a plain accessor) does not trip."""

        class _Getter:
            def get(self) -> None: ...

        assert not StoreInventory.is_keyed_store(_Getter)

    def test_plain_class_does_not_trip(self) -> None:
        class _Plain:
            def run(self) -> None: ...

        assert not StoreInventory.is_keyed_store(_Plain)

    # -- _lifecycle_imports ---------------------------------------------------

    def test_run_state_read_model_import_does_not_trip(self) -> None:
        """RunState is a RunHistory projection, not a checkpoint (PIR-872)."""
        matched = StoreInventory._lifecycle_imports(
            "from pirn_agents.sessions.run_state import RunState\n"
        )
        assert matched == ()

    def test_run_checkpoint_import_trips(self) -> None:
        matched = StoreInventory._lifecycle_imports(
            "from pirn_agents.sessions.run_checkpoint import RunCheckpoint\n"
        )
        assert "RunCheckpoint" in matched

    def test_cassette_name_import_trips(self) -> None:
        matched = StoreInventory._lifecycle_imports(
            "from pirn_agents.determinism.cassette import Cassette\n"
        )
        assert "Cassette" in matched

    def test_cassette_module_import_trips(self) -> None:
        matched = StoreInventory._lifecycle_imports(
            "from pirn_agents.determinism.cassette_store import CassetteStore\n"
        )
        assert "CassetteStore" in matched

    def test_bare_cassette_module_import_trips(self) -> None:
        matched = StoreInventory._lifecycle_imports("import pirn_agents.determinism.cassette\n")
        assert matched

    def test_unrelated_import_does_not_trip(self) -> None:
        matched = StoreInventory._lifecycle_imports(
            "from pirn_agents.sessions.session_message import SessionMessage\n"
        )
        assert matched == ()

    def test_lifecycle_import_parses_real_syntax(self) -> None:
        """Sanity: the scanner is real AST, not a substring match on the source."""
        source = (
            "# This module talks about RunState in a comment, not an import.\n"
            "from pirn_agents.sessions.session_message import SessionMessage\n"
        )
        assert StoreInventory._lifecycle_imports(source) == ()
        tree_source = "from pirn_agents.sessions.run_checkpoint import RunCheckpoint\n"
        assert ast.parse(tree_source) is not None
        assert "RunCheckpoint" in StoreInventory._lifecycle_imports(tree_source)
