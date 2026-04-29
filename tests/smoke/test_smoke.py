"""Smoke tests — package imports, public surface, quickstart works."""

from __future__ import annotations


def test_package_imports():
    import pirn

    assert pirn.__version__ == "0.3.0"


def test_core_public_surface():
    from pirn import (
        Knot,
        Optional,
        knot,
    )

    # Spot-check that they are the right kinds of things.
    assert isinstance(Knot, type)
    assert callable(knot)
    assert isinstance(Optional, type)


def test_node_public_surface():
    from pirn import (
        Aggregator,
        Branch,
        BranchOutput,
        Gate,
        Map,
        Reduce,
        Sink,
        Source,
    )

    for cls in (Source, Sink, Aggregator, Branch, BranchOutput, Gate, Map, Reduce):
        assert isinstance(cls, type)


def test_backend_public_surface():
    from pirn import (
        DataStore,
        InMemoryDataStore,
        InMemoryHistory,
        InMemoryStore,
        RunHistory,
        TapestryStore,
    )

    # Protocols are runtime_checkable; instances of the InMemory variants
    # should satisfy isinstance.
    assert isinstance(InMemoryStore(), TapestryStore)
    assert isinstance(InMemoryHistory(), RunHistory)
    assert isinstance(InMemoryDataStore(), DataStore)


def test_dispatcher_public_surface():
    from pirn import Dispatcher, LocalDispatcher, ThreadDispatcher

    assert isinstance(LocalDispatcher(), Dispatcher)
    d = ThreadDispatcher()
    try:
        assert isinstance(d, Dispatcher)
    finally:
        d.shutdown()


def test_yaml_public_surface():
    from pirn import PipelineSpec, load_pipeline

    assert callable(load_pipeline)
    assert isinstance(PipelineSpec, type)


async def test_quickstart_example():
    """The simplest possible pipeline; mirrors the README quickstart."""
    from pirn import KnotConfig, Parameter, RunRequest, Tapestry, knot

    @knot
    async def double(x: int) -> int:
        return x * 2

    with Tapestry() as t:
        p = Parameter("x", int, default=21)
        double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest())
    assert result.outputs["d"] == 42


def test_phase3_emitter_public_surface():
    """Phase 3 emitter classes are importable from the package root."""
    from pirn import (
        Emitter,
        KafkaEmitter,
        LogEmitter,
        OpenTelemetryEmitter,
        ValKeyEmitter,
        WebhookEmitter,
    )

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
    """Phase 3 trigger classes are importable from the package root."""
    from pirn import (
        CronTrigger,
        KafkaTrigger,
        Trigger,
        ValKeyTrigger,
        WebhookTrigger,
        run_forever,
    )

    for cls in (CronTrigger, KafkaTrigger, ValKeyTrigger, WebhookTrigger):
        assert isinstance(cls, type)
    assert callable(run_forever)
    assert isinstance(Trigger, type)  # Protocol class


def test_phase3_log_emitter_works_without_extras():
    """LogEmitter has no optional dependencies — it should construct
    cleanly even without any [extras] installed."""
    from pirn import LogEmitter

    e = LogEmitter()
    assert e.name == "LogEmitter"
