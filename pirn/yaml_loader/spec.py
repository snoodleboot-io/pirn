"""Pydantic schema for YAML pipeline declarations.

Each node has a ``type`` discriminator and type-specific fields.  Parents
are referenced by knot id.  The schema is validated by Pydantic before
we attempt to instantiate any knots.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NodeSpec(BaseModel):
    """Common fields for all node types."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    error_policy: str = "skip_if_parent_failed"
    validate_io: bool = True


class ParameterSpec(NodeSpec):
    type: Literal["parameter"]
    type_: str = Field(
        ...,
        description="Python type as a dotted path (e.g. 'int', 'str', "
        "'list[dict]', 'my_pkg.MyType').",
    )
    default: Any = None
    has_default: bool = False


class SourceSpec(NodeSpec):
    type: Literal["source"]
    callable: str = Field(
        ...,
        description="Dotted path to a callable that will be wrapped with "
        "@knot to produce the source's process() method.  Loose mode "
        "(allow_callable_refs=True) is required to use this.",
    )


class KnotSpec(NodeSpec):
    type: Literal["knot"]
    callable: str = Field(
        ...,
        description="Dotted path to the function/Knot class.  Requires "
        "loose mode unless registered in the loader's known_knots map.",
    )
    parents: dict[str, str] = Field(
        default_factory=dict,
        description="Map of input-name -> parent-knot-id.",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Map of input-name -> constant config value.",
    )


class SinkSpec(NodeSpec):
    type: Literal["sink"]
    callable: str
    parents: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class AggregatorSpec(NodeSpec):
    type: Literal["aggregator"]
    combine: str = Field(
        ...,
        description="Dotted path to the combine callable.  Loose mode required.",
    )
    parents: dict[str, str] = Field(default_factory=dict)


class BranchSpec(NodeSpec):
    type: Literal["branch"]
    input: str = Field(..., description="Knot id of the input.")
    selector: str = Field(..., description="Dotted path to the selector callable.")
    branches: list[str] = Field(..., min_length=1)


class GateSpec(NodeSpec):
    type: Literal["gate"]
    input: str
    predicate: str


class MapSpec(NodeSpec):
    type: Literal["map"]
    over: str = Field(..., description="Knot id producing the collection.")
    each: str = Field(..., description="Dotted path to inner Knot class or @knot factory.")
    bind: str
    shared: dict[str, Any] = Field(default_factory=dict)


class ReduceSpec(NodeSpec):
    type: Literal["reduce"]
    of: str = Field(..., description="Knot id producing the list.")
    combine: str
    initial: Any = None
    has_initial: bool = False


# Discriminated union — Pydantic picks the right model based on `type`.
NodeSpecUnion = (
    ParameterSpec
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
    """Top-level pipeline declaration.

    ``allow_callable_refs`` enables loose mode: callables/predicates/
    selectors specified as dotted paths are imported at load time.
    Without it, only nodes that don't reference Python callables
    (parameters, branches with named selectors registered ahead of
    time, etc.) work.
    """

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
