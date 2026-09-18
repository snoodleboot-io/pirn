"""Unit tests for :class:`ScadaSeriesSpec`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from pirn_oilgas.types.scada_series_spec import ScadaSeriesSpec

_ROWS = [(datetime(2026, 1, 1, tzinfo=UTC), 1.0), (datetime(2026, 1, 1, 0, 1, tzinfo=UTC), 2.0)]


class TestConstruction(unittest.TestCase):
    def test_full_values(self) -> None:
        spec = ScadaSeriesSpec(label="oil", rows=_ROWS, tag="oil-tag")
        assert spec.label == "oil"
        assert spec.rows == _ROWS
        assert spec.tag == "oil-tag"

    def test_requires_label(self) -> None:
        with pytest.raises(ValidationError):
            ScadaSeriesSpec(rows=_ROWS, tag="oil-tag")

    def test_requires_rows(self) -> None:
        with pytest.raises(ValidationError):
            ScadaSeriesSpec(label="oil", tag="oil-tag")

    def test_requires_tag(self) -> None:
        with pytest.raises(ValidationError):
            ScadaSeriesSpec(label="oil", rows=_ROWS)


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        spec = ScadaSeriesSpec(label="oil", rows=_ROWS, tag="oil-tag")
        with pytest.raises(ValidationError):
            spec.tag = "new-tag"
