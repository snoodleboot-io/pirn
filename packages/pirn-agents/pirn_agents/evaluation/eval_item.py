"""``EvalItem`` — one input/gold-output case in an eval dataset."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class EvalItem(PirnOpaqueValue):
    """A single evaluation case: an input, its gold output, and metadata.

    Attributes
    ----------
    item_id:
        Stable identifier for the case; also the default cassette key for
        deterministic replay (F29).
    input:
        The input mapping fed to the pattern/pipeline under test.
    expected:
        The gold output mapping metrics compare the produced output against.
    metadata:
        Free-form per-item metadata (difficulty, tags, source) not used for
        scoring but carried through to the report.
    """

    item_id: str
    input: Mapping[str, Any]
    expected: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate field types.

        Raises:
            TypeError: If ``item_id`` is not a str or ``input``/``expected``/
                ``metadata`` are not mappings.
        """
        if not isinstance(self.item_id, str):
            raise TypeError(f"EvalItem.item_id must be a str, got {type(self.item_id).__name__}")
        for name in ("input", "expected", "metadata"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise TypeError(f"EvalItem.{name} must be a mapping, got {type(value).__name__}")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "input": dict(self.input),
            "expected": dict(self.expected),
            "metadata": dict(self.metadata),
        }
