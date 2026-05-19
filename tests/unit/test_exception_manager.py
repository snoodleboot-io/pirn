"""ExceptionManager tests."""

from __future__ import annotations
import unittest

from pirn.managers.exception_manager import ExceptionManager



class _StandaloneTests(unittest.TestCase):
    def test_records_an_exception(self):
        em = ExceptionManager(run_id="r1")
        try:
            raise ValueError("boom")
        except ValueError as e:
            rec = em.record(knot_id="k1", exc=e)
        assert rec.run_id == "r1"
        assert rec.knot_id == "k1"
        assert rec.exc_type == "ValueError"
        assert rec.message == "boom"
        assert "ValueError" in rec.traceback_text
        assert rec.id.startswith("exc-")
    
    
    def test_record_id_is_unique(self):
        em = ExceptionManager(run_id="r1")
        rec1 = em.record("k1", ValueError("a"))
        rec2 = em.record("k2", ValueError("b"))
        assert rec1.id != rec2.id
    
    
    def test_get_by_id(self):
        em = ExceptionManager(run_id="r1")
        rec = em.record("k1", ValueError("x"))
        assert em.get(rec.id) is rec
        assert em.get("not-a-real-id") is None
    
    
    def test_report_returns_all_in_order(self):
        em = ExceptionManager(run_id="r1")
        a = em.record("k1", ValueError("a"))
        b = em.record("k2", RuntimeError("b"))
        rep = em.report()
        assert rep == [a, b]
    
    
    def test_has_failures_and_len(self):
        em = ExceptionManager(run_id="r1")
        assert not em.has_failures()
        assert len(em) == 0
        em.record("k", ValueError("x"))
        assert em.has_failures()
        assert len(em) == 1
    
    
    def test_rebindable_exception_carries_original_type_and_traceback(self):
        """A ``RebindableError`` (used by the engine when rebinding a
        placeholder record produced by a knot in isolation) is recognised by
        the manager: the carried ``original_exc_type`` and
        ``original_traceback_text`` surface on the new record rather than
        the wrapper's own type and frames."""
        from pirn.managers.rebindable_exception import RebindableError
    
        em = ExceptionManager(run_id="r1")
        exc = RebindableError(
            exc_type="OriginalErrorType",
            message="rebound message",
            traceback_text="<original traceback text>",
        )
        rec = em.record("k", exc)
        assert rec.exc_type == "OriginalErrorType"
        assert rec.traceback_text == "<original traceback text>"
        assert rec.message == "rebound message"
    
    
    def test_ordinary_exception_uses_its_own_type_and_traceback(self):
        """Non-RebindableError exceptions surface ``type(exc).__name__``
        and the live traceback rather than any carried metadata."""
        em = ExceptionManager(run_id="r1")
        try:
            raise ValueError("real error")
        except ValueError as e:
            rec = em.record("k", e)
        assert rec.exc_type == "ValueError"
        assert "ValueError" in rec.traceback_text
        assert rec.message == "real error"
