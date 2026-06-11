"""Acceptance test for SCD-01: global registry-key uniqueness.

`sweet_tea`'s ``Registry.register`` keys every class by ``class_name.lower()``
under a ``library`` (``"pirn"`` for this project). ``BaseFactory.create`` raises
``SweetTeaError`` when more than one entry matches a ``(key, library)`` pair, so
any duplicate makes bare-name YAML resolution of that knot fail at runtime.

This is the executable definition of the SCD-01 gate: every ``(key, library)``
pair must resolve to exactly one distinct class across the whole registered knot
set. The test imports :mod:`pirn`, which triggers ``Registry.fill_registry`` at
package import time, then asserts there are no collisions.
"""

from __future__ import annotations

from collections import defaultdict

import pirn  # noqa: F401 — import triggers Registry.fill_registry() at package init
from sweet_tea.registry import Registry


def _collisions() -> dict[tuple[str, str], set[str]]:
    """Map every ``(key, library)`` with >1 distinct class to those class paths."""
    by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    for entry in Registry.entries():
        fully_qualified = f"{entry.class_def.__module__}.{entry.class_def.__name__}"
        by_pair[(entry.key, entry.library)].add(fully_qualified)
    return {pair: classes for pair, classes in by_pair.items() if len(classes) > 1}


def test_registry_keys_are_globally_unique() -> None:
    """No ``(key, library)`` pair maps to more than one distinct class."""
    # Arrange — registry is populated by importing pirn (module import above).
    # Act
    collisions = _collisions()

    # Assert
    assert not collisions, (
        "Duplicate registry keys break bare-name resolution "
        f"(create() raises on >1 match). {len(collisions)} collision(s):\n"
        + "\n".join(
            f"  ({key!r}, {library!r}) -> "
            + ", ".join(sorted(classes))
            for (key, library), classes in sorted(collisions.items())
        )
    )
