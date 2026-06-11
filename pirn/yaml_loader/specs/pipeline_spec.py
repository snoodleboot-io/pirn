from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pirn.yaml_loader.specs.aggregator_spec import AggregatorSpec
from pirn.yaml_loader.specs.branch_spec import BranchSpec
from pirn.yaml_loader.specs.gate_spec import GateSpec
from pirn.yaml_loader.specs.knot_spec import KnotSpec
from pirn.yaml_loader.specs.map_spec import MapSpec
from pirn.yaml_loader.specs.reduce_spec import ReduceSpec
from pirn.yaml_loader.specs.sink_spec import SinkSpec
from pirn.yaml_loader.specs.source_spec import SourceSpec
from pirn.yaml_loader.specs.yaml_parameter_spec import YamlParameterSpec

NodeSpecUnion = (
    YamlParameterSpec
    | SourceSpec
    | KnotSpec
    | SinkSpec
    | AggregatorSpec
    | BranchSpec
    | GateSpec
    | MapSpec
    | ReduceSpec
)


class PipelineSpec(BaseModel):
    """Top-level pipeline declaration."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    allow_callable_refs: bool = False
    allowed_module_prefixes: list[str] | None = Field(
        default=None,
        description="When allow_callable_refs is True, only callable refs whose module path "
        "starts with one of these prefixes may be imported. None means no restriction.",
    )
    nodes: list[NodeSpecUnion] = Field(default_factory=list)

    @property
    def nodes_by_id(self) -> dict[str, NodeSpecUnion]:
        return {n.id: n for n in self.nodes}
