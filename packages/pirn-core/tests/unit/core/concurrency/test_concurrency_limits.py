"""Unit tests for ConcurrencyLimits (PIR-841 slice 2)."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits


class TestConcurrencyLimitsDefaults(unittest.TestCase):
    def test_default_is_unbounded(self) -> None:
        # Arrange / Act
        limits = ConcurrencyLimits()

        # Assert
        self.assertIsNone(limits.max_in_flight)
        self.assertEqual(dict(limits.groups), {})
        self.assertTrue(limits.is_unbounded)

    def test_a_global_cap_is_bounded(self) -> None:
        # Arrange / Act
        limits = ConcurrencyLimits(max_in_flight=8)

        # Assert
        self.assertEqual(limits.max_in_flight, 8)
        self.assertFalse(limits.is_unbounded)

    def test_a_group_cap_is_bounded(self) -> None:
        # Arrange / Act
        limits = ConcurrencyLimits(groups={"api": 4})

        # Assert
        self.assertEqual(limits.group_limit("api"), 4)
        self.assertFalse(limits.is_unbounded)

    def test_a_group_without_a_cap_has_no_limit(self) -> None:
        # Arrange
        limits = ConcurrencyLimits(groups={"api": 4})

        # Act / Assert
        self.assertIsNone(limits.group_limit("db"))
        self.assertIsNone(limits.group_limit(None))

    def test_accepts_a_cap_of_one(self) -> None:
        # Arrange / Act
        limits = ConcurrencyLimits(max_in_flight=1, groups={"api": 1})

        # Assert
        self.assertEqual(limits.max_in_flight, 1)
        self.assertEqual(limits.group_limit("api"), 1)


class TestConcurrencyLimitsValidation(unittest.TestCase):
    def test_rejects_a_zero_global_cap(self) -> None:
        with self.assertRaises(ValidationError):
            ConcurrencyLimits(max_in_flight=0)

    def test_rejects_a_negative_global_cap(self) -> None:
        with self.assertRaises(ValidationError):
            ConcurrencyLimits(max_in_flight=-3)

    def test_rejects_a_bool_global_cap(self) -> None:
        # True == 1 in Python; a flag is never a meaningful cap.
        with self.assertRaises(ValidationError):
            ConcurrencyLimits(max_in_flight=True)

    def test_rejects_a_float_global_cap(self) -> None:
        with self.assertRaises(ValidationError):
            ConcurrencyLimits(max_in_flight=2.5)  # type: ignore[arg-type]

    def test_rejects_a_zero_group_cap(self) -> None:
        with self.assertRaises(ValidationError):
            ConcurrencyLimits(groups={"api": 0})

    def test_rejects_a_negative_group_cap(self) -> None:
        with self.assertRaises(ValidationError):
            ConcurrencyLimits(groups={"api": -1})

    def test_rejects_a_bool_group_cap(self) -> None:
        with self.assertRaises(ValidationError):
            ConcurrencyLimits(groups={"api": True})

    def test_rejects_group_names_outside_the_knot_id_charset(self) -> None:
        for bad in ["", "a b", "a/b", "a\nb", "x" * 257]:
            with self.subTest(name=bad), self.assertRaises(ValidationError):
                ConcurrencyLimits(groups={bad: 2})

    def test_accepts_group_names_in_the_knot_id_charset(self) -> None:
        for good in ["api", "open-ai", "tenant.a", "ns:llm", "A_1"]:
            with self.subTest(name=good):
                self.assertEqual(ConcurrencyLimits(groups={good: 2}).group_limit(good), 2)

    def test_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ConcurrencyLimits(max_inflight=3)  # type: ignore[call-arg]


class TestConcurrencyLimitsImmutability(unittest.TestCase):
    def test_fields_cannot_be_reassigned(self) -> None:
        # Arrange
        limits = ConcurrencyLimits(max_in_flight=2)

        # Act / Assert
        with self.assertRaises(ValidationError):
            limits.max_in_flight = 3

    def test_groups_cannot_be_mutated_in_place(self) -> None:
        # Arrange
        limits = ConcurrencyLimits(groups={"api": 2})

        # Act / Assert
        with self.assertRaises(TypeError):
            limits.groups["api"] = 99  # type: ignore[index]

    def test_mutating_the_source_mapping_does_not_change_the_limits(self) -> None:
        # Arrange
        source = {"api": 2}
        limits = ConcurrencyLimits(groups=source)

        # Act
        source["api"] = 99

        # Assert
        self.assertEqual(limits.group_limit("api"), 2)


class TestConcurrencyLimitsSerialization(unittest.TestCase):
    def test_round_trips_through_json(self) -> None:
        # Arrange: a trigger carries limits on a RunRequest as JSON.
        limits = ConcurrencyLimits(max_in_flight=8, groups={"api": 4})

        # Act
        restored = ConcurrencyLimits.model_validate_json(limits.model_dump_json())

        # Assert
        self.assertEqual(restored.max_in_flight, 8)
        self.assertEqual(dict(restored.groups), {"api": 4})

    def test_equal_limits_compare_equal(self) -> None:
        self.assertEqual(
            ConcurrencyLimits(max_in_flight=2, groups={"a": 1}),
            ConcurrencyLimits(max_in_flight=2, groups={"a": 1}),
        )


if __name__ == "__main__":
    unittest.main()
