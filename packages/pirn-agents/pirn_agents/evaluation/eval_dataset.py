"""``EvalDataset`` — an ordered, JSON-round-trippable set of eval items."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.evaluation.eval_item import EvalItem


@dataclass(frozen=True)
class EvalDataset(PirnOpaqueValue):
    """A fixture dataset of :class:`EvalItem`\\ s the runner evaluates.

    The dataset format is deliberately plain JSON (a list of items, each with an
    ``item_id``, ``input``, ``expected``, and optional ``metadata``) so fixtures
    are readable, diffable, and checked into the repo.

    Attributes
    ----------
    items:
        The evaluation cases, in dataset order (item ids must be unique).
    """

    items: tuple[EvalItem, ...] = ()

    def __post_init__(self) -> None:
        """Validate, normalise, and uniqueness-check the items.

        Raises:
            TypeError: If ``items`` is not a sequence of :class:`EvalItem`.
            ValueError: If two items share an ``item_id``.
        """
        if isinstance(self.items, (str, bytes)) or not isinstance(self.items, Sequence):
            raise TypeError(
                f"EvalDataset.items must be a sequence of EvalItem, got {type(self.items).__name__}"
            )
        items = tuple(self.items)
        seen: set[str] = set()
        for index, item in enumerate(items):
            if not isinstance(item, EvalItem):
                raise TypeError(
                    f"EvalDataset.items[{index}] must be an EvalItem, got {type(item).__name__}"
                )
            if item.item_id in seen:
                raise ValueError(f"EvalDataset: duplicate item_id {item.item_id!r}")
            seen.add(item.item_id)
        object.__setattr__(self, "items", items)

    def __len__(self) -> int:
        return len(self.items)

    @classmethod
    def from_json(cls, data: str) -> EvalDataset:
        """Reconstruct a dataset from its :meth:`to_json` form."""
        payload = json.loads(data)
        items = tuple(
            EvalItem(
                item_id=entry["item_id"],
                input=dict(entry.get("input", {})),
                expected=dict(entry.get("expected", {})),
                metadata=dict(entry.get("metadata", {})),
            )
            for entry in payload.get("items", [])
        )
        return cls(items=items)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise the dataset to a stable, machine-readable JSON string."""
        payload = {"items": [item._pirn_audit_dict() for item in self.items]}
        return json.dumps(payload, indent=indent, sort_keys=True)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"items": [item._pirn_audit_dict() for item in self.items]}
