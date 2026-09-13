"""Enumerate every knot marked ``_is_stub`` and pin the expected count.

PIR-856 (SHOULD): a set of knots across the health domain are documented
stand-ins for a vendor implementation ("Production version uses X; this
stub ...") but were registered as ordinary production knots with nothing
distinguishing them from a real implementation. Every such class now
carries ``_is_stub: ClassVar[bool] = True``. This test walks the whole
``pirn_health`` package to discover them, so the count stays visible and a
future change that silently adds, removes, or forgets a stub marker is
caught rather than drifting unnoticed.

See ``docs/domains/health.md`` ("Reference stubs" section) for the
narrative list.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import unittest

import pirn_health

# Pinned by the PIR-856 stub audit: genomics 18, mri 7, trials 7, clinical 6,
# pathology 1. (The ticket's own tally read "clinical 5"; this repo includes
# ClinicalNLPExtractor as a 6th because its own docstring documents a stub
# fallback path, even though its primary path calls a live LLM provider --
# erring toward flagging it rather than silently excluding a self-documented
# stub.)
_EXPECTED_STUB_COUNT = 39


def _discover_stub_classes() -> list[type]:
    """Import every module under ``pirn_health`` and collect classes that
    declare ``_is_stub = True`` in their own ``__dict__`` (not inherited)."""
    stubs: list[type] = []
    assert pirn_health.__path__ is not None
    for module_info in pkgutil.walk_packages(pirn_health.__path__, prefix="pirn_health."):
        module = importlib.import_module(module_info.name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__:
                continue  # count a class only in the module that defines it
            if vars(obj).get("_is_stub") is True:
                stubs.append(obj)
    return stubs


class TestReferenceStubs(unittest.TestCase):
    def test_stub_count_is_pinned(self) -> None:
        stubs = _discover_stub_classes()
        names = sorted({cls.__qualname__ for cls in stubs})
        assert len(names) == _EXPECTED_STUB_COUNT, (
            f"expected {_EXPECTED_STUB_COUNT} documented stubs, found {len(names)}: {names}"
        )

    def test_every_stub_is_a_knot(self) -> None:
        from pirn.core.knot import Knot

        for cls in _discover_stub_classes():
            assert issubclass(cls, Knot), (
                f"{cls.__qualname__} is marked _is_stub=True but is not a Knot subclass"
            )

    def test_every_stub_documents_itself_as_a_stub(self) -> None:
        for cls in _discover_stub_classes():
            module_doc = inspect.getmodule(cls).__doc__ or ""
            assert "stub" in module_doc.lower(), (
                f"{cls.__qualname__} is marked _is_stub=True but its module "
                "docstring does not mention 'stub'"
            )
            assert "Note:" in module_doc, (
                f"{cls.__qualname__} is marked _is_stub=True but its module "
                "docstring has no Note: block explaining the marker"
            )
