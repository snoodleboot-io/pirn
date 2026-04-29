"""YAML pipeline loader.

Strict by default: every node has a known type, every field is validated.
Loose mode (opt-in via ``allow_callable_refs=True``) permits dotted-path
imports of arbitrary Python callables.
"""

from pirn.yaml_loader.loader import load_pipeline
from pirn.yaml_loader.spec import (
    AggregatorSpec,
    BranchSpec,
    GateSpec,
    KnotSpec,
    MapSpec,
    NodeSpec,
    PipelineSpec,
    ReduceSpec,
    SinkSpec,
    SourceSpec,
)
from pirn.yaml_loader.spec import (
    ParameterSpec as ParameterNodeSpec,
)

__all__ = [
    "AggregatorSpec",
    "BranchSpec",
    "GateSpec",
    "KnotSpec",
    "MapSpec",
    "NodeSpec",
    "ParameterNodeSpec",
    "PipelineSpec",
    "ReduceSpec",
    "SinkSpec",
    "SourceSpec",
    "load_pipeline",
]
