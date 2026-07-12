"""Unit tests for :class:`MemoryProvenance`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn_agents.memory_management.memory_provenance import MemoryProvenance


class TestMemoryProvenanceValidation(unittest.TestCase):
    def test_rejects_empty_source(self) -> None:
        with self.assertRaises(TypeError):
            MemoryProvenance(source="", timestamp=datetime(2026, 1, 1, tzinfo=UTC))

    def test_rejects_non_datetime_timestamp(self) -> None:
        with self.assertRaises(TypeError):
            MemoryProvenance(source="s", timestamp="2026")  # type: ignore[arg-type]

    def test_rejects_out_of_range_trust(self) -> None:
        with self.assertRaises(ValueError):
            MemoryProvenance(
                source="s", timestamp=datetime(2026, 1, 1, tzinfo=UTC), trust_signal=1.5
            )

    def test_rejects_bool_trust(self) -> None:
        with self.assertRaises(TypeError):
            MemoryProvenance(
                source="s", timestamp=datetime(2026, 1, 1, tzinfo=UTC), trust_signal=True
            )


class TestMemoryProvenanceRoundTrip(unittest.TestCase):
    def test_payload_round_trips(self) -> None:
        original = MemoryProvenance(
            source="consolidator",
            timestamp=datetime(2026, 6, 1, 12, tzinfo=UTC),
            trust_signal=0.8,
            derivation="consolidated-from:a,b",
        )
        restored = MemoryProvenance.from_payload(original.to_payload())
        assert restored == original

    def test_from_payload_defaults_trust(self) -> None:
        restored = MemoryProvenance.from_payload(
            {"source": "s", "timestamp": datetime(2026, 1, 1, tzinfo=UTC).isoformat()}
        )
        assert restored.trust_signal == 1.0

    def test_from_payload_rejects_non_mapping(self) -> None:
        with self.assertRaises(TypeError):
            MemoryProvenance.from_payload("nope")
