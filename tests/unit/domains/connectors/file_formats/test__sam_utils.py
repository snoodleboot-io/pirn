"""Tests for :class:`_SamUtils`."""

from __future__ import annotations

import os
import unittest

from pirn.domains.connectors.file_formats._sam_utils import _SamUtils


class TestSamUtilsWriteTempfile(unittest.TestCase):
    def test_write_tempfile_creates_file(self) -> None:
        path = _SamUtils.write_tempfile(b"hello", suffix=".sam")
        self.addCleanup(_SamUtils.safe_unlink, path)
        self.assertTrue(os.path.exists(path))
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"hello")

    def test_write_tempfile_respects_suffix(self) -> None:
        path = _SamUtils.write_tempfile(b"data", suffix=".bam")
        self.addCleanup(_SamUtils.safe_unlink, path)
        self.assertTrue(path.endswith(".bam"))


class TestSamUtilsMakeTempfilePath(unittest.TestCase):
    def test_creates_empty_file(self) -> None:
        path = _SamUtils.make_tempfile_path(suffix=".tmp")
        self.addCleanup(_SamUtils.safe_unlink, path)
        self.assertTrue(os.path.exists(path))

    def test_respects_suffix(self) -> None:
        path = _SamUtils.make_tempfile_path(suffix=".cram")
        self.addCleanup(_SamUtils.safe_unlink, path)
        self.assertTrue(path.endswith(".cram"))


class TestSamUtilsSafeUnlink(unittest.TestCase):
    def test_safe_unlink_removes_file(self) -> None:
        path = _SamUtils.make_tempfile_path(suffix=".tmp")
        _SamUtils.safe_unlink(path)
        self.assertFalse(os.path.exists(path))

    def test_safe_unlink_nonexistent_does_not_raise(self) -> None:
        _SamUtils.safe_unlink("/tmp/does_not_exist_pirn_test_12345.tmp")


class TestSamUtilsValidateRecord(unittest.TestCase):
    def _valid_record(self):
        return {
            "qname": "read1", "flag": 0, "rname": "chr1", "pos": 1,
            "mapq": 60, "cigar": "10M", "rnext": "*", "pnext": 0,
            "tlen": 0, "seq": "ACGTACGTAC", "qual": "IIIIIIIIII",
        }

    def test_valid_record_passes(self) -> None:
        _SamUtils.validate_record(self._valid_record())

    def test_missing_field_raises_value_error(self) -> None:
        rec = self._valid_record()
        del rec["qname"]
        with self.assertRaises(ValueError):
            _SamUtils.validate_record(rec)


class TestSamUtilsInferHeader(unittest.TestCase):
    def test_infer_header_produces_sq_entries(self) -> None:
        import unittest.mock as mock
        pysam_stub = mock.MagicMock()
        records = [
            {"rname": "chr1", "pos": 100, "seq": "ACGT", "mapq": 0,
             "flag": 0, "qname": "r1", "cigar": "4M", "rnext": "*",
             "pnext": 0, "tlen": 0, "qual": "*"},
        ]
        header = _SamUtils.infer_header(pysam_stub, records)
        self.assertIn("SQ", header)
        self.assertEqual(header["SQ"][0]["SN"], "chr1")

    def test_infer_header_no_records_uses_chr1_fallback(self) -> None:
        import unittest.mock as mock
        pysam_stub = mock.MagicMock()
        header = _SamUtils.infer_header(pysam_stub, [])
        self.assertEqual(header["SQ"][0]["SN"], "chr1")
