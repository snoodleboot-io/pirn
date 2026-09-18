"""Unit tests for :class:`GenomicsRecord`."""

from __future__ import annotations

import unittest

from pirn.core.content_hasher import ContentHasher

from pirn_health.types.genomics_record import GenomicsRecord


class TestConstruction(unittest.TestCase):
    def test_default(self) -> None:
        record = GenomicsRecord()
        assert record.sample_id == ""
        assert record.locus == ""
        assert record.genotype == ""
        assert record.quality_score == 0.0

    def test_full(self) -> None:
        record = GenomicsRecord(
            sample_id="S1",
            locus="chr1:1000",
            genotype="A/T",
            quality_score=42.5,
        )
        assert record.sample_id == "S1"
        assert record.locus == "chr1:1000"
        assert record.genotype == "A/T"
        assert record.quality_score == 42.5


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_primitives(self) -> None:
        record = GenomicsRecord(
            sample_id="S1",
            locus="chr1:1000",
            genotype="A/T",
            quality_score=42.5,
        )
        d = record._pirn_audit_dict()
        assert d["locus"] == "chr1:1000"
        assert d["genotype"] == "A/T"
        assert d["quality_score"] == 42.5
        for value in d.values():
            assert isinstance(value, (str, int, float, list, type(None)))

    def test_audit_dict_never_carries_the_raw_sample_id(self) -> None:
        record = GenomicsRecord(
            sample_id="NA12878", locus="chr1:1000", genotype="A/T", quality_score=42.5
        )

        d = record._pirn_audit_dict()

        assert "sample_id" not in d
        assert "NA12878" not in repr(d)
        assert d["sample_id_hash"] == ContentHasher.hash("NA12878")

    def test_two_samples_stay_distinguishable_in_lineage(self) -> None:
        """Dropping the identifier outright would collapse these two into one hash."""
        first = GenomicsRecord(
            sample_id="NA12878", locus="chr1:1000", genotype="A/T", quality_score=42.5
        )
        second = GenomicsRecord(
            sample_id="NA12891", locus="chr1:1000", genotype="A/T", quality_score=42.5
        )

        assert first._pirn_audit_dict() != second._pirn_audit_dict()
        assert ContentHasher.hash(first) != ContentHasher.hash(second)


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        record = GenomicsRecord()
        try:
            record.sample_id = "X"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("GenomicsRecord must be frozen")
