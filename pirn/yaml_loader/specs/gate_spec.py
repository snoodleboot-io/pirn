from __future__ import annotations

from typing import Literal

from pirn.yaml_loader.specs.node_spec import NodeSpec


class GateSpec(NodeSpec):
    type: Literal["gate"]
    input: str
    predicate: str
