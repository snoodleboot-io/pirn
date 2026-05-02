"""Unit tests for :class:`SourceFrame`."""

from __future__ import annotations

from pirn.domains.signal.types.source_frame import SourceFrame


class TestRoundtrip:
    def test_construct_with_defaults(self) -> None:
        frame = SourceFrame()
        assert frame.signal_id == ""
        assert frame.source_count == 0
        assert frame.mixing_matrix_shape == (0, 0)

    def test_construct_with_full_kwargs(self) -> None:
        frame = SourceFrame(
            signal_id="sig-1",
            source_count=3,
            mixing_matrix_shape=(4, 3),
        )
        assert frame.signal_id == "sig-1"
        assert frame.source_count == 3
        assert frame.mixing_matrix_shape == (4, 3)

    def test_audit_dict_serialises_shape_as_list(self) -> None:
        frame = SourceFrame(
            signal_id="sig-2",
            source_count=2,
            mixing_matrix_shape=(2, 2),
        )
        d = frame._pirn_audit_dict()
        assert d == {
            "signal_id": "sig-2",
            "source_count": 2,
            "mixing_matrix_shape": [2, 2],
        }

    def test_frozen_disallows_mutation(self) -> None:
        frame = SourceFrame(signal_id="x")
        try:
            frame.signal_id = "y"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("SourceFrame should be frozen")
