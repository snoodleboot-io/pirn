"""Tests for :class:`pirn.yaml_loader.knot_resolver.KnotResolver`.

Three of the tests below are marked ``xfail`` and tied to the upstream
sweet_tea issue documented in
``planning/current/sweet_tea_change_request.md``: ``Registry`` caches
``typed_entries(lookup_type=Knot)`` on first query and never refreshes
that cache when subsequent ``register()`` calls add new ``Knot``
subclasses. Pirn's ``fill_registry()`` at import primes the cache before
these tests can register their own probe classes, so the probes are
invisible to the resolver until upstream lands the fix.

When the sweet_tea fix is released, these tests will start passing —
remove the ``xfail`` markers at that point.
"""

from __future__ import annotations

import pytest
from sweet_tea.registry import Registry

from pirn.core.knot import Knot
from pirn.yaml_loader.knot_resolver import KnotResolver


_SWEET_TEA_CACHE_REASON = (
    "blocked by sweet_tea Registry cache staleness; see "
    "planning/current/sweet_tea_change_request.md"
)


class _ResolverProbeKnot(Knot):
    """Concrete Knot used only by these tests."""

    async def process(self, **_):
        return None


class TestKnotResolver:
    @pytest.mark.xfail(reason=_SWEET_TEA_CACHE_REASON, strict=False)
    def test_resolves_class_registered_under_snake_case_key(self) -> None:
        Registry.register(
            "_resolver_probe_knot",
            _ResolverProbeKnot,
            library="pirn_test",
        )
        resolver = KnotResolver()
        assert resolver.has("_resolver_probe_knot")
        assert resolver.get_class("_resolver_probe_knot") is _ResolverProbeKnot

    @pytest.mark.xfail(reason=_SWEET_TEA_CACHE_REASON, strict=False)
    def test_resolves_class_via_camelcase_variation(self) -> None:
        # Sweet_tea generates a snake_case variant from CamelCase input,
        # so a class registered under "_resolver_probe_knot" also matches
        # when looked up as "_ResolverProbeKnot".
        Registry.register(
            "_resolver_probe_knot",
            _ResolverProbeKnot,
            library="pirn_test",
        )
        resolver = KnotResolver()
        assert resolver.has("_ResolverProbeKnot")

    def test_unknown_name_returns_false_and_raises(self) -> None:
        resolver = KnotResolver()
        assert resolver.has("definitely_not_registered") is False
        try:
            resolver.get_class("definitely_not_registered")
        except KeyError as exc:
            assert "definitely_not_registered" in str(exc)
        else:
            raise AssertionError("expected KeyError")

    @pytest.mark.xfail(reason=_SWEET_TEA_CACHE_REASON, strict=False)
    def test_library_filter_scopes_resolution(self) -> None:
        Registry.register(
            "_library_filtered_knot",
            _ResolverProbeKnot,
            library="pirn_test_other",
        )
        # Default resolver: library is None, matches any library.
        assert KnotResolver().has("_library_filtered_knot")

        # Filter by a non-matching library: must miss.
        scoped = KnotResolver(library="some_other_project")
        assert scoped.has("_library_filtered_knot") is False

        # Filter by the matching library: must hit.
        matching = KnotResolver(library="pirn_test_other")
        assert matching.has("_library_filtered_knot")

    def test_construct_with_lowercased_library(self) -> None:
        # sweet_tea lowercases library on registration; the resolver should
        # mirror that so case-insensitive comparisons work.
        resolver = KnotResolver(library="MyProject")
        assert resolver.library == "myproject"
