"""Pins what makes `import pirn_agents` expensive, so it cannot grow unnoticed.

PIR-780 asked whether the eager ``Registry.fill_registry`` call in
``pirn_agents/__init__.py`` should be replaced by a manifest-driven fill,
on the theory that importing the 271-module ``specializations`` tree is what
costs ~1.2 s. Measurement refuted that. On this machine, against the tree at
the time of writing::

    import pirn (core) + sweet_tea only ............................  613 ms
    + walk & import all 779 pirn_agents modules, register nothing ...  750 ms
    + register 680 entries with an O(1) duplicate check .............  785 ms
    + register 680 entries as sweet_tea actually does .............. 2190 ms

So of the ~1.58 s the eager fill adds, importing the modules is ~0.14 s (9 %)
and building the ``Entry`` objects is ~0.04 s (2 %). The remaining ~1.40 s
(89 %) is ``Registry.register``'s duplicate check, ``new_entry not in
cls.__registry``: a linear scan of a list of pydantic models, run once per
registration, so quadratic in the size of the *global* registry. It is
quadratic across packages too — the registry is process-wide, so every domain
package pays for the entries the ones imported before it added.

A manifest would therefore buy back ~0.14 s of a ~2.2 s import while adding a
build step and a staleness risk; making the duplicate check O(1) upstream buys
~1.40 s and changes no design. The numbers are on PIR-780.

What this module guards, in consequence, is the *inputs* to that cost, all
measured structurally rather than on the clock (the benchmark suite is excluded
from the default gate precisely because wall-clock assertions are unreliable on
a loaded machine — see PIR-810/PIR-777):

* how many modules the eager fill imports,
* how many entries it registers — the term that gets squared,
* how many ``Entry`` comparisons the import performs in total.

The bounds are ceilings with headroom, not exact pins: they exist to catch a
step change, not to be rewritten every time a knot is added. If a fix lands in
``sweet_tea`` the comparison count collapses toward zero and the ceiling still
holds, so this test does not have to be touched to accept the improvement.

Distinct from ``test_import_dependency_closure``, which asserts *what* a bare
import may load. This asserts *how much*.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from functools import lru_cache

# Ceilings, with roughly 25 % headroom over the values measured at the time of
# writing: 779 modules, 272 of them specializations; 1099 entries (419 from
# pirn-core, 680 from pirn_agents); 603 351 comparisons, which is exactly
# 1099 x 1098 / 2.
_MAX_PIRN_AGENTS_MODULES = 975
_MAX_SPECIALIZATION_MODULES = 340
_MAX_REGISTRY_ENTRIES = 1375

# n^2/2 at the entry ceiling, so the two bounds bind at the same point rather
# than one firing first and masking the other. Stated as its own number rather
# than computed, because the relationship is sweet_tea's implementation detail:
# if sweet_tea makes the duplicate check O(1) the count collapses and this
# ceiling still holds, which is the point. It also catches a second filler —
# re-running fill_registry over an already-filled registry roughly doubles the
# comparisons without adding a single entry.
_MAX_ENTRY_COMPARISONS = 950_000

# Sanity floors. A probe that observed nothing would make every ceiling above
# vacuous, and that failure mode is silent.
_MIN_PIRN_AGENTS_MODULES = 100
_MIN_REGISTRY_ENTRIES = 100

_PROBE = r"""
import json
import sys
import warnings

from sweet_tea.entry import Entry
from sweet_tea.registry import Registry

# Count how often two registry entries are compared. sweet_tea's duplicate
# check drives this; wrapping __eq__ observes it without assuming which
# container or algorithm does the checking.
_base_eq = Entry.__eq__
_comparisons = 0


def _counting_eq(self, other):
    global _comparisons
    _comparisons += 1
    return _base_eq(self, other)


Entry.__eq__ = _counting_eq

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import pirn_agents  # noqa: F401

modules = [m for m in sys.modules if m.startswith("pirn_agents")]
print(json.dumps({
    "comparisons": _comparisons,
    "entries": len(Registry.entries()),
    "modules": len(modules),
    "specializations": len(
        [m for m in modules if m.startswith("pirn_agents.specializations")]
    ),
}))
"""


@lru_cache(maxsize=1)
def _probe() -> dict[str, int]:
    """Return the import-cost inputs measured in a fresh interpreter.

    A subprocess is required, not a convenience: this test module's own imports
    have already filled the registry and populated ``sys.modules``, so an
    in-process measurement would read zero for everything. Cached because the
    subprocess pays the very ~2 s import this module is about, and all four
    cases read the same measurement.
    """
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE], capture_output=True, text=True, check=True
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


class TestImportCost(unittest.TestCase):
    def setUp(self) -> None:
        self.measured = _probe()

    def test_the_probe_actually_observes_the_import(self) -> None:
        # Guards the ceilings below: all of them pass trivially against zeros.
        assert self.measured["modules"] >= _MIN_PIRN_AGENTS_MODULES, self.measured
        assert self.measured["entries"] >= _MIN_REGISTRY_ENTRIES, self.measured
        assert self.measured["specializations"] > 0, self.measured

    def test_eager_fill_imports_a_bounded_number_of_modules(self) -> None:
        modules = self.measured["modules"]
        assert modules <= _MAX_PIRN_AGENTS_MODULES, (
            f"`import pirn_agents` now imports {modules} modules, over the "
            f"{_MAX_PIRN_AGENTS_MODULES} ceiling. Registry.fill_registry imports the "
            f"whole tree eagerly, so every module added anywhere under pirn_agents is "
            f"paid for by every user on every import. Raise the ceiling only with a "
            f"fresh measurement (PIR-780)."
        )
        specializations = self.measured["specializations"]
        assert specializations <= _MAX_SPECIALIZATION_MODULES, (
            f"the specializations tree grew to {specializations} modules, over the "
            f"{_MAX_SPECIALIZATION_MODULES} ceiling."
        )

    def test_eager_fill_registers_a_bounded_number_of_entries(self) -> None:
        # The term that gets squared. sweet_tea registers *every* class defined
        # in each visited module, not only Knot subclasses, so this grows faster
        # than the knot catalog does.
        entries = self.measured["entries"]
        assert entries <= _MAX_REGISTRY_ENTRIES, (
            f"`import pirn_agents` now fills the registry with {entries} entries, over "
            f"the {_MAX_REGISTRY_ENTRIES} ceiling. Registration cost is quadratic in "
            f"this number (PIR-780), so this is the number to watch, not the module "
            f"count."
        )

    def test_registration_does_not_get_more_quadratic(self) -> None:
        comparisons = self.measured["comparisons"]
        assert comparisons <= _MAX_ENTRY_COMPARISONS, (
            f"filling the registry now performs {comparisons} Entry comparisons, over "
            f"the {_MAX_ENTRY_COMPARISONS} ceiling. sweet_tea's Registry.register "
            f"checks for duplicates with `new_entry not in cls.__registry` — a linear "
            f"scan of pydantic models — so this is n^2/2 in the registry size and is "
            f"~89 % of the import cost (PIR-780). If it grew, either the tree gained "
            f"entries or something started re-filling the registry."
        )
