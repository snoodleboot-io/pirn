"""``RaptorTree`` — a built RAPTOR summary tree handle.

The value a RAPTOR build returns: a content-addressed handle describing the tree
that now lives in the vector store. ``ContentHasher.hash`` keys the tree by its leaf
corpus, so re-ingesting identical content is detected and skipped (``reused``).

``RaptorTree`` is ``Payload[RaptorTreeFrame, RaptorNode | None]`` (PIR-868
pattern, applied by PIR-874; ADR agents-speaks-core WS6b): the frame carries the
content hash, node/level counts and ``reused`` flag; ``data`` is the root summary
node (``None`` for an empty or reused build). The constructor keeps the named
fields; read them back as ``metadata.<field>`` and ``data``.
"""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.rag.indexing.raptor_node import RaptorNode
from pirn_agents.specializations.rag.indexing.raptor_tree_frame import RaptorTreeFrame


class RaptorTree(AgentResult[RaptorTreeFrame, RaptorNode | None]):
    """A built RAPTOR tree descriptor (frame) plus its root node (data)."""

    def __init__(
        self,
        content_hash: str,
        node_count: int,
        level_count: int,
        reused: bool,
        root: RaptorNode | None = None,
    ) -> None:
        frame = RaptorTreeFrame(
            content_hash=content_hash,
            node_count=node_count,
            level_count=level_count,
            reused=reused,
        )
        if root is not None and not isinstance(root, RaptorNode):
            raise TypeError(
                f"RaptorTree: root must be a RaptorNode or None, got {type(root).__name__}"
            )
        super().__init__(metadata=frame, data=root)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["root"] = None if self.data is None else self._audit_form(self.data)
        return audit
