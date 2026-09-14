"""``PromptChainFrame`` — lineage metadata for a :class:`PromptChainResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class PromptChainFrame(PirnOpaqueValue):
    """Run-level facts for a sequential prompt chain.

    The frame half of the ``Payload[PromptChainFrame, str]`` split (PIR-868).

    Attributes
    ----------
    outputs:
        The output of each link in the chain, in order.
    """

    outputs: tuple[str, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"outputs": list(self.outputs)}
