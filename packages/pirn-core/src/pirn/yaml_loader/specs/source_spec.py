from __future__ import annotations

from typing import Literal

from pydantic import Field

from pirn.yaml_loader.specs.node_spec import NodeSpec


class SourceSpec(NodeSpec):
    type: Literal["source"]
    callable: str = Field(
        ...,
        description="Dotted path to a callable wrapped with @knot.  Loose mode required.",
    )
