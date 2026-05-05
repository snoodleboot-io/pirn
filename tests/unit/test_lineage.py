"""KnotLineage record tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from pirn.core.lineage import KnotLineage


def _make(**overrides):
    base = dict(
        run_id="r1",
        knot_id="k1",
        knot_class="my_module.MyKnot",
        knot_config_hash="sha256:cfg",
        outcome="ok",
        dispatcher="LocalDispatcher",
        output_hash="sha256:out",
    )
    base.update(overrides)
    return KnotLineage(**base)



class _StandaloneTests(unittest.TestCase):
    def test_minimal_ok_record(self):
        rec = _make()
        assert rec.outcome == "ok"
        assert rec.succeeded is True
        assert rec.error_record_id is None
        assert rec.skip_reason is None
    
    
    def test_err_record(self):
        rec = _make(outcome="err", output_hash=None, error_record_id="exc-abc")
        assert not rec.succeeded
        assert rec.error_record_id == "exc-abc"
    
    
    def test_skipped_record(self):
        rec = _make(outcome="skipped", output_hash=None, skip_reason="branch_not_selected")
        assert not rec.succeeded
        assert rec.skip_reason == "branch_not_selected"
    
    
    def test_record_is_frozen(self):
        import pytest
        from pydantic import ValidationError
    
        rec = _make()
        with self.assertRaises(ValidationError):
            rec.knot_id = "k2"
    
    
    def test_duration_ms(self):
        start = datetime.now(UTC)
        end = start + timedelta(milliseconds=250)
        rec = _make(started_at=start, finished_at=end)
        assert 240 < rec.duration_ms < 260
    
    
    def test_parent_input_hashes_default_empty(self):
        rec = _make()
        assert rec.parent_input_hashes == {}
    
    
    def test_extra_dict_default_empty(self):
        rec = _make()
        assert rec.extra == {}
