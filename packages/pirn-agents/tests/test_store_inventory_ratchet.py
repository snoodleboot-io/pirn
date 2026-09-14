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
* every module importing ``RunState``, ``RunCheckpoint``, or a ``*Cassette*``
  name — the session/determinism value shapes a future workstream replaces
  with ``RunResult``/``ReplaySession`` adapters.

Both allowlists are asserted by **exact equality**: a new entry fails because
it is not in the list (growth caught); removing/renaming a store or importer
without updating the list also fails, because the list still names it
(the burn-down is visible here, one line at a time).
"""

from __future__ import annotations

import ast
import unittest

from tests.store_inventory import StoreInventory

# --- known keyed stores, frozen ---------------------------------------------
# Regenerate by running StoreInventory.discover_store_classes() from the
# package root (packages/pirn-agents) and pasting the sorted keys below.

STORE_CLASSES = frozenset(
    {
        "caching/in_memory_result_cache.py::InMemoryResultCache",
        "caching/result_cache.py::ResultCache",
        "caching/semantic_result_cache.py::SemanticResultCache",
        # ADR agents-speaks-core WS2: a vended similarity INDEX (a PirnOpaqueValue
        # resource like the vector backends); it maps embeddings to content_hash
        # keys and holds no values — values live in core DataStore. Not a KV store.
        "caching/vector_memo_index.py::VectorMemoIndex",
        "connectors/streaming_s3_store.py::StreamingS3Store",
        "memory/stores/data_store_memory_store.py::DataStoreMemoryStore",
        # ADR agents-speaks-core WS3 part 4: the keyed-identity primitive every
        # other keyed store (DataStoreMemoryStore, SemanticMemoryUpsert,
        # CrossSessionProfileUpdater) now delegates to — a caller-chosen key is
        # a knot id, backed by RunHistory/DataStore, not a hashed row in a KV
        # table. ThreadRepository/PersistedSessionStore/SessionStore/
        # InMemorySessionStore/CassetteStore/InMemoryCassetteStore/
        # FileCassetteStore/BatchCheckpointer -- the one-cycle shims this store
        # existed to eventually replace -- are deleted (PIR-864).
        "memory/stores/keyed_lineage_store.py::KeyedLineageStore",
        "memory/stores/memory_store.py::MemoryStore",
        "retrieval/vector_stores/chroma_memory_store.py::ChromaMemoryStore",
        "retrieval/vector_stores/in_memory_vector_store.py::InMemoryVectorStore",
        "retrieval/vector_stores/pgvector_memory_store.py::PgvectorMemoryStore",
        "retrieval/vector_stores/qdrant_memory_store.py::QdrantMemoryStore",
        "retrieval/vector_stores/vector_memory_store.py::VectorMemoryStore",
    }
)

# --- known RunState/RunCheckpoint/Cassette* importers, frozen ---------------
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
# leaving two real, non-deprecated importers: batch/batch_progress.py (its
# to_run_state()/from_run_state() bridge, kept for a possible future durable
# caller — see its module docstring) and sessions/run_resumer.py.
LIFECYCLE_IMPORTERS = frozenset(
    {
        "batch/batch_progress.py",
        "sessions/run_resumer.py",
    }
)


class TestStoreInventoryIsFrozen(unittest.TestCase):
    """Freeze the keyed-store and lifecycle-importer inventories. Exact equality."""

    def test_the_store_walk_is_not_vacuous(self) -> None:
        """A guard that finds nothing passes for the wrong reason."""
        found = StoreInventory.discover_store_classes()
        assert len(found) >= 10, len(found)

    def test_the_importer_walk_is_not_vacuous(self) -> None:
        # PIR-864 deleted five of the seven prior importers (one-cycle shims);
        # two real importers remain -- see LIFECYCLE_IMPORTERS above.
        found = StoreInventory.discover_lifecycle_importers()
        assert len(found) >= 2, len(found)

    def test_keyed_store_classes_are_frozen(self) -> None:
        found = frozenset(StoreInventory.discover_store_classes())
        assert found == STORE_CLASSES, {
            "new keyed stores": sorted(found - STORE_CLASSES),
            "shrunk — remove from STORE_CLASSES": sorted(STORE_CLASSES - found),
        }

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

    def test_run_state_import_trips(self) -> None:
        matched = StoreInventory._lifecycle_imports(
            "from pirn_agents.sessions.run_state import RunState\n"
        )
        assert "RunState" in matched

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
        tree_source = "from pirn_agents.sessions.run_state import RunState\n"
        assert ast.parse(tree_source) is not None
        assert "RunState" in StoreInventory._lifecycle_imports(tree_source)
