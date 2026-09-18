"""Memory keys are content-addressed through ``ContentHasher``, and time is injected.

Five places computed their own ``hashlib`` digest beside
``pirn.core.content_hasher.ContentHasher`` — the workspace's one
content-addressing seam — so a key derived in one place and a hash of the same
value computed anywhere else disagreed. Two writers also read the wall clock
(``datetime.now(UTC)``) inside ``process()``, which no deterministic run can
reproduce. Both are PIR-873 findings.

These assert the observable consequences: a key a caller can recompute with
``ContentHasher`` alone, and a ``stored_at`` a ``FrozenClock`` pins.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pirn.core.content_hasher import ContentHasher
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.determinism.deterministic_rng import DeterministicRng
from pirn_agents.determinism.frozen_clock import FrozenClock
from pirn_agents.memory.management.memory_consolidator import MemoryConsolidator
from pirn_agents.memory.management.near_duplicate_grouper import NearDuplicateGrouper
from pirn_agents.memory.patterns.procedural_memory_writer import ProceduralMemoryWriter
from pirn_agents.memory.patterns.semantic_fact_writer import SemanticFactWriter
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.memory_management.conftest import RecordingMemoryStore, StubSummarizer, make_record


class TestKeysAreRecomputableWithContentHasher:
    """A caller holding the value can derive the key without knowing the writer."""

    async def test_a_semantic_fact_key_is_the_content_hash_of_the_fact(self) -> None:
        # Arrange
        store = RecordingMemoryStore()
        with Tapestry() as tapestry:
            writer = SemanticFactWriter(
                facts=["the sky is blue"], store=store, _config=KnotConfig(id="sfw")
            )

        # Act
        await tapestry.run(RunRequest(), terminals=writer)

        # Assert
        assert store.stored == [f"semantic:{ContentHasher.hash('the sky is blue')}"]

    async def test_a_procedure_key_is_the_content_hash_of_the_task(self) -> None:
        # Arrange
        store = RecordingMemoryStore()
        with Tapestry():
            writer = ProceduralMemoryWriter(
                agent_response=AgentResponse(content="step 1"),
                task_description="deploy the app",
                store=store,
                _config=KnotConfig(id="pmw"),
            )

        # Act
        key = await writer.process(
            agent_response=AgentResponse(content="step 1"),
            task_description="deploy the app",
            store=store,
        )

        # Assert
        assert key == f"procedure:{ContentHasher.hash('deploy the app')}"

    async def test_a_consolidated_id_is_the_content_hash_of_its_source_ids(self) -> None:
        # Arrange
        records = [
            make_record(id="a1", content="alpha beta gamma", kind="episodic"),
            make_record(id="a2", content="alpha beta gamma delta", kind="episodic"),
        ]
        with Tapestry() as tapestry:
            consolidator = MemoryConsolidator(
                records=records,
                summarizer=StubSummarizer(),
                grouper=NearDuplicateGrouper(threshold=0.5),
                _config=KnotConfig(id="consolidator"),
            )

        # Act
        run = await tapestry.run(RunRequest(), terminals=consolidator)

        # Assert
        (merged,) = run.outputs["consolidator"]
        assert merged.data.id == f"semantic:consolidated:{ContentHasher.hash(('a1', 'a2'))}"

    def test_an_unusable_call_id_is_hashed_through_content_hasher(self) -> None:
        # Arrange — a call id ``KnotConfig`` refuses, so it must be hashed.
        call_id = "call/with spaces?"

        # Act
        knot_id = ToolFactory.knot_id_for(call_id)

        # Assert
        digest = ContentHasher.hash(call_id).removeprefix("sha256:")
        assert knot_id == f"call-{digest[:16]}"
        assert KnotConfig(id=knot_id).id == knot_id

    def test_a_usable_call_id_is_left_alone(self) -> None:
        assert ToolFactory.knot_id_for("call_1") == "call_1"


class TestTimeIsInjectedNotRead:
    async def test_a_frozen_clock_pins_a_semantic_fact_timestamp(self) -> None:
        # Arrange
        store = RecordingMemoryStore()
        frozen = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
        with Tapestry() as tapestry:
            writer = SemanticFactWriter(
                facts=["a"],
                store=store,
                clock=FrozenClock(epoch=frozen),
                _config=KnotConfig(id="sfw"),
            )

        # Act
        await tapestry.run(RunRequest(), terminals=writer)

        # Assert
        assert [entry["stored_at"] for entry in store.data.values()] == [frozen.isoformat()]

    async def test_a_frozen_clock_pins_a_procedure_timestamp(self) -> None:
        # Arrange
        store = RecordingMemoryStore()
        frozen = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
        with Tapestry():
            writer = ProceduralMemoryWriter(
                agent_response=AgentResponse(content="step 1"),
                task_description="deploy the app",
                store=store,
                clock=FrozenClock(epoch=frozen),
                _config=KnotConfig(id="pmw"),
            )

        # Act
        key = await writer.process(
            agent_response=AgentResponse(content="step 1"),
            task_description="deploy the app",
            store=store,
            clock=FrozenClock(epoch=frozen),
        )

        # Assert
        assert store.data[key]["stored_at"] == frozen.isoformat()

    async def test_without_a_clock_the_timestamp_is_still_a_real_instant(self) -> None:
        # Arrange — the default is a ``SystemClock``, never a bare ``datetime.now``.
        store = RecordingMemoryStore()
        with Tapestry():
            writer = ProceduralMemoryWriter(
                agent_response=AgentResponse(content="step 1"),
                task_description="deploy the app",
                store=store,
                _config=KnotConfig(id="pmw"),
            )

        # Act
        key = await writer.process(
            agent_response=AgentResponse(content="step 1"),
            task_description="deploy the app",
            store=store,
        )

        # Assert
        stamped = datetime.fromisoformat(store.data[key]["stored_at"])
        assert stamped.tzinfo is not None


class TestForkedSeedsComeFromTheSameSeam:
    def test_a_forked_seed_is_the_content_hash_of_seed_and_label(self) -> None:
        # Arrange / Act
        child = DeterministicRng(seed=99).fork("a")

        # Assert
        digest = ContentHasher.hash((99, "a")).removeprefix("sha256:")
        assert child.seed == int(digest[:16], 16)

    def test_forks_stay_reproducible_and_independent(self) -> None:
        parent = DeterministicRng(seed=99)
        assert parent.fork("a").seed == DeterministicRng(seed=99).fork("a").seed
        assert parent.fork("a").seed != parent.fork("b").seed
