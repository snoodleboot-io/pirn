"""``AssembledContext`` is ``Payload[AssembledContextFrame, tuple[ContextItem, ...]]`` (PIR-874)."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_agents.context.assembled_context import AssembledContext
from pirn_agents.context.assembled_context_frame import AssembledContextFrame
from pirn_agents.context.context_item import ContextItem

_A = ContextItem(content="a", position=1)
_B = ContextItem(content="b", position=2)


def _make(kept: tuple[ContextItem, ...] = (_B,)) -> AssembledContext:
    return AssembledContext(kept=kept, evicted=(_A,), total_tokens=1)


class TestAssembledContext:
    def test_is_a_payload_with_a_frame(self) -> None:
        ctx = _make()
        assert isinstance(ctx, Payload)
        assert isinstance(ctx.metadata, AssembledContextFrame)

    def test_frame_carries_run_facts_and_data_the_kept_items(self) -> None:
        ctx = _make()
        assert ctx.metadata.total_tokens == 1
        assert ctx.metadata.evicted == (_A,)
        assert ctx.data == (_B,)

    def test_audit_dict_has_both_halves(self) -> None:
        audit = _make()._pirn_audit_dict()
        assert audit["total_tokens"] == 1
        assert audit["evicted"] == [_A._pirn_audit_dict()]
        assert audit["kept"] == [_B._pirn_audit_dict()]

    def test_equality_is_structural(self) -> None:
        assert _make() == _make()
        assert _make() != _make(kept=())
        assert _make() != object()
