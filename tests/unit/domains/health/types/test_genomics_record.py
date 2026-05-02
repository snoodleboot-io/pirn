"""Unit tests for :class:`GenomicsRecord`."""

from __future__ import annotations

from pirn.domains.health.types.genomics_record import GenomicsRecord


class TestConstruction:
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


class TestAuditDict:
    def test_audit_dict_primitives(self) -> None:
        record = GenomicsRecord(
            sample_id="S1",
            locus="chr1:1000",
            genotype="A/T",
            quality_score=42.5,
        )
        d = record._pirn_audit_dict()
        assert d["sample_id"] == "S1"
        assert d["locus"] == "chr1:1000"
        assert d["genotype"] == "A/T"
        assert d["quality_score"] == 42.5
        for value in d.values():
            assert isinstance(value, (str, int, float, list, type(None)))


class TestFrozen:
    def test_frozen_disallows_mutation(self) -> None:
        record = GenomicsRecord()
        try:
            record.sample_id = "X"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("GenomicsRecord must be frozen")
