"""Unit tests for :class:`DICOMSeries`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.domains.health.types.dicom_series import DICOMSeries


class TestConstruction(unittest.TestCase):
    def test_default(self) -> None:
        series = DICOMSeries()
        assert series.study_uid == ""
        assert series.series_uid == ""
        assert series.modality == ""
        assert series.num_frames == 0

    def test_full(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        series = DICOMSeries(
            study_uid="ST",
            series_uid="SE",
            modality="MR",
            num_frames=128,
            fetched_at=when,
        )
        assert series.study_uid == "ST"
        assert series.series_uid == "SE"
        assert series.modality == "MR"
        assert series.num_frames == 128
        assert series.fetched_at == when


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_primitives(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        series = DICOMSeries(
            study_uid="ST",
            series_uid="SE",
            modality="MR",
            num_frames=128,
            fetched_at=when,
        )
        d = series._pirn_audit_dict()
        assert d["study_uid"] == "ST"
        assert d["series_uid"] == "SE"
        assert d["modality"] == "MR"
        assert d["num_frames"] == 128
        assert d["fetched_at"] == when.isoformat()
        for value in d.values():
            assert isinstance(value, (str, int, float, list, type(None)))


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        series = DICOMSeries()
        try:
            series.study_uid = "X"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("DICOMSeries must be frozen")
