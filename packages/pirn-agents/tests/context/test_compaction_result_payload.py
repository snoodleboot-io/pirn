"""``CompactionResult`` is ``Payload[CompactionFrame, tuple[ContextItem, ...]]`` (PIR-874)."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_agents.context.compaction_frame import CompactionFrame
from pirn_agents.context.compaction_result import CompactionResult
from pirn_agents.context.context_item import ContextItem

_OLD = ContextItem(content="old", position=1)
_SUMMARY = ContextItem(content="sum", kind="summary", position=1, pinned=True)


def _make(triggered: bool = True) -> CompactionResult:
    return CompactionResult(
        retained=(_SUMMARY,),
        evicted=(_OLD,),
        summary="sum",
        summary_item=_SUMMARY,
        triggered=triggered,
        tokens_before=10,
        tokens_after=2,
    )


class TestCompactionResult:
    def test_is_a_payload_with_a_frame(self) -> None:
        result = _make()
        assert isinstance(result, Payload)
        assert isinstance(result.metadata, CompactionFrame)

    def test_frame_fields_and_data(self) -> None:
        result = _make()
        assert result.metadata.triggered is True
        assert result.metadata.tokens_before == 10
        assert result.metadata.tokens_after == 2
        assert result.metadata.summary == "sum"
        assert result.metadata.summary_item == _SUMMARY
        assert result.metadata.evicted == (_OLD,)
        assert result.data == (_SUMMARY,)

    def test_audit_dict_has_both_halves(self) -> None:
        audit = _make()._pirn_audit_dict()
        assert audit["triggered"] is True
        assert audit["summary_item"] == _SUMMARY._pirn_audit_dict()
        assert audit["evicted"] == [_OLD._pirn_audit_dict()]
        assert audit["retained"] == [_SUMMARY._pirn_audit_dict()]

    def test_audit_dict_with_no_summary_item(self) -> None:
        result = CompactionResult(
            retained=(_OLD,),
            evicted=(),
            summary="",
            summary_item=None,
            triggered=False,
            tokens_before=1,
            tokens_after=1,
        )
        assert result._pirn_audit_dict()["summary_item"] is None

    def test_equality_is_structural(self) -> None:
        assert _make() == _make()
        assert _make() != _make(triggered=False)
