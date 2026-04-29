"""pirn — a pipeline framework where everything is a knot.

Phase 3 public API.

Phase 3 adds:

* Networked persistence backends (SQLite, DuckDB, Postgres, ValKey,
  S3, local disk) — imported from ``pirn.backends.<name>``.  Each
  backend is an optional dependency; install via ``pip install
  pirn[sqlite]`` etc.
* Distributed dispatchers (Dask, Ray, Celery) — imported from
  ``pirn.engine.<name>_dispatcher``.
* Triggers and emitters (``pirn.triggers``, ``pirn.emitters``) for
  event-driven runs and run observation.
* Visualisation (``pirn.viz``).
"""

from pirn.backends import DataStore, RunHistory, TapestrySnapshot, TapestryStore
from pirn.backends.in_memory import (
    InMemoryDataStore,
    InMemoryHistory,
    InMemoryStore,
)
from pirn.core.config import ErrorPolicy, KnotConfig
from pirn.core.context import RunContext, RunRequest, RunResult
from pirn.core.hashing import UNHASHABLE, content_hash
from pirn.core.knot import Knot, KnotFactory, Optional, knot
from pirn.core.lineage import KnotLineage
from pirn.core.parameter import Parameter, ParameterSpec
from pirn.core.result import Err, Ok, Result, Skipped

# Phase 3 — emitters and triggers.  These submodules import lazily,
# so re-exporting at the package root is safe even when optional deps
# (kafka, valkey-glide, httpx) aren't installed: the inner classes
# raise ImportError only when *used*.
from pirn.emitters import (
    Emitter,
    KafkaEmitter,
    LogEmitter,
    OpenTelemetryEmitter,
    ValKeyEmitter,
    WebhookEmitter,
)
from pirn.engine.dispatcher import Dispatcher, LocalDispatcher, ThreadDispatcher
from pirn.engine.engine import Engine
from pirn.managers.exceptions import (
    ExceptionManager,
    ExceptionRecord,
    RebindableException,
)
from pirn.managers.status import KnotState, StatusEvent, StatusManager
from pirn.nodes import (
    Aggregator,
    Branch,
    BranchOutput,
    Gate,
    Map,
    Reduce,
    Sink,
    Source,
)
from pirn.replay import KnotDiff, compare_runs, replay_run
from pirn.streaming import (
    FileTailSource,
    IterableSource,
    StreamingSource,
    StreamingSourceTrigger,
    run_stream,
)
from pirn.tapestry import Tapestry, current_tapestry
from pirn.triggers import (
    CronTrigger,
    KafkaTrigger,
    Trigger,
    ValKeyTrigger,
    WebhookTrigger,
    run_forever,
)
from pirn.viz import html_for_run, mermaid_for_run, mermaid_for_tapestry
from pirn.yaml_loader import PipelineSpec, load_pipeline

__version__ = "0.3.0"

__all__ = [
    # Core
    "Knot",
    "knot",
    "KnotFactory",
    "Optional",
    "ErrorPolicy",
    "KnotConfig",
    "Parameter",
    "ParameterSpec",
    "Result",
    "Ok",
    "Err",
    "Skipped",
    "content_hash",
    "UNHASHABLE",
    # Lineage
    "KnotLineage",
    # Tapestry
    "Tapestry",
    "current_tapestry",
    # Run lifecycle
    "RunContext",
    "RunRequest",
    "RunResult",
    # Engine
    "Engine",
    "Dispatcher",
    "LocalDispatcher",
    "ThreadDispatcher",
    # Managers
    "ExceptionManager",
    "ExceptionRecord",
    "RebindableException",
    "StatusManager",
    "StatusEvent",
    "KnotState",
    # Backends
    "TapestryStore",
    "RunHistory",
    "DataStore",
    "TapestrySnapshot",
    "InMemoryStore",
    "InMemoryHistory",
    "InMemoryDataStore",
    # Node types
    "Source",
    "Sink",
    "Aggregator",
    "Branch",
    "BranchOutput",
    "Gate",
    "Map",
    "Reduce",
    # YAML
    "PipelineSpec",
    "load_pipeline",
    # Phase 3 — emitters
    "Emitter",
    "LogEmitter",
    "KafkaEmitter",
    "ValKeyEmitter",
    "WebhookEmitter",
    "OpenTelemetryEmitter",
    # Phase 3 — triggers
    "Trigger",
    "CronTrigger",
    "KafkaTrigger",
    "ValKeyTrigger",
    "WebhookTrigger",
    "run_forever",
    # Phase 3 — streaming
    "StreamingSource",
    "IterableSource",
    "FileTailSource",
    "StreamingSourceTrigger",
    "run_stream",
    # Phase 3 — visualization
    "mermaid_for_tapestry",
    "mermaid_for_run",
    "html_for_run",
    # Replay and diff
    "replay_run",
    "compare_runs",
    "KnotDiff",
    # Version
    "__version__",
]
