"""Smoke tests — package imports, public surface, quickstart works."""

from __future__ import annotations


def test_package_imports():
    import pirn

    assert pirn.__version__ == "0.3.0"


def test_core_public_surface():
    from pirn.core.knot import Knot
    from pirn.core.knot_factory import knot
    from pirn.core.optional import Optional

    # Spot-check that they are the right kinds of things.
    assert isinstance(Knot, type)
    assert callable(knot)
    assert isinstance(Optional, type)


def test_node_public_surface():
    from pirn.nodes.aggregator import Aggregator
    from pirn.nodes.branch.branch import Branch
    from pirn.nodes.branch.branch_output import BranchOutput
    from pirn.nodes.gate.gate import Gate
    from pirn.nodes.map_markers import DictMap, Map, ZipMap
    from pirn.nodes.reduce_ import Reduce
    from pirn.nodes.sink import Sink
    from pirn.nodes.source import Source

    for cls in (Source, Sink, Aggregator, Branch, BranchOutput, Gate, Map, ZipMap, DictMap, Reduce):
        assert isinstance(cls, type)


def test_backend_public_surface():
    from pirn.backends.base.data_store import DataStore
    from pirn.backends.base.run_history import RunHistory
    from pirn.backends.base.tapestry_store import TapestryStore
    from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
    from pirn.backends.in_memory.in_memory_history import InMemoryHistory
    from pirn.backends.in_memory.in_memory_store import InMemoryStore

    # Protocols are runtime_checkable; instances of the InMemory variants
    # should satisfy isinstance.
    assert isinstance(InMemoryStore(), TapestryStore)
    assert isinstance(InMemoryHistory(), RunHistory)
    assert isinstance(InMemoryDataStore(), DataStore)


def test_dispatcher_public_surface():
    from pirn.engine.dispatchers.dispatcher import Dispatcher
    from pirn.engine.dispatchers.local_dispatcher import LocalDispatcher
    from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher

    assert isinstance(LocalDispatcher(), Dispatcher)
    d = ThreadDispatcher()
    try:
        assert isinstance(d, Dispatcher)
    finally:
        d.shutdown()


def test_yaml_public_surface():
    from pirn.yaml_loader.loader import load_pipeline
    from pirn.yaml_loader.specs.pipeline_spec import PipelineSpec

    assert callable(load_pipeline)
    assert isinstance(PipelineSpec, type)


async def test_quickstart_example():
    """The simplest possible pipeline; mirrors the README quickstart."""
    from pirn.core.knot_config import KnotConfig
    from pirn.core.knot_factory import knot
    from pirn.core.parameter import Parameter
    from pirn.core.run_request import RunRequest
    from pirn.tapestry import Tapestry

    @knot
    async def double(x: int) -> int:
        return x * 2

    with Tapestry() as t:
        p = Parameter("x", int, default=21)
        double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest())
    assert result.outputs["d"] == 42


def test_phase3_emitter_public_surface():
    """Phase 3 emitter classes are importable from their defining modules."""
    from pirn.emitters.base import Emitter
    from pirn.emitters.kafka import KafkaEmitter
    from pirn.emitters.log import LogEmitter
    from pirn.emitters.otel import OpenTelemetryEmitter
    from pirn.emitters.valkey import ValKeyEmitter
    from pirn.emitters.webhook import WebhookEmitter

    for cls in (
        Emitter,
        LogEmitter,
        KafkaEmitter,
        ValKeyEmitter,
        WebhookEmitter,
        OpenTelemetryEmitter,
    ):
        assert isinstance(cls, type)


def test_phase3_trigger_public_surface():
    """Phase 3 trigger classes are importable from their defining modules."""
    from pirn.triggers.base import Trigger, run_forever
    from pirn.triggers.cron import CronTrigger
    from pirn.triggers.http import WebhookTrigger
    from pirn.triggers.kafka import KafkaTrigger
    from pirn.triggers.valkey import ValKeyTrigger

    for cls in (CronTrigger, KafkaTrigger, ValKeyTrigger, WebhookTrigger):
        assert isinstance(cls, type)
    assert callable(run_forever)
    assert isinstance(Trigger, type)  # Protocol class


def test_phase3_log_emitter_works_without_extras():
    """LogEmitter has no optional dependencies — it should construct
    cleanly even without any [extras] installed."""
    from pirn.emitters.log import LogEmitter

    e = LogEmitter()
    assert e.name == "LogEmitter"
