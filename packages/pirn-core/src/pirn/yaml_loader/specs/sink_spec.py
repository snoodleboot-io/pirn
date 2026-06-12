from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from pirn.yaml_loader.specs.node_spec import NodeSpec


class SinkSpec(NodeSpec):
    type: Literal["sink"]
    callable: str
    parents: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
