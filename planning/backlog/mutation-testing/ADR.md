# ADR: Mutation Testing

**Status:** TBD — to be written when sprint starts
**Initiative:** mutation-testing

---

## Context

`mutmut` is configured but running it unfiltered against the full test suite produces noise. The current configuration mutates all of `pirn/` without filtering, which means:

1. Pure-delegation knots (methods that do nothing but call a library function) generate mutants that survive because the unit tests assert structure but not numerical correctness. These are not real test gaps — they are inherent to the pirn architecture where the library call is the domain logic.
2. Abstract interface files (`lineage_store.py`, `embedding_provider.py`, etc.) have no concrete implementation in pirn and thus no tests. Mutmut reports all mutants in these files as surviving, inflating the failure count.
3. A full run takes several hours, making it impractical for CI without scoping.

Key decisions needed before the mutation testing initiative can produce actionable results.

---

## Open Architectural Questions

**1. Which modules should be gated in CI vs run on a nightly schedule?**

`pirn/core/` (framework primitives, Payload, Assembler, SubTapestry contract, KnotRegistry) is the highest-value target: bugs here affect every user. This is small enough for a CI run on every PR. Domain libraries are larger and noisier; they are better candidates for the nightly run. The decision must specify the exact module list for each schedule, including how to handle new modules as domains expand.

**2. What kill-rate threshold to require per module?**

Kill rate = (killed mutants) / (total mutants). A 100% target is impractical for delegation-heavy code; a 50% target is too low to be meaningful. Reasonable starting points: `pirn/core/` at ≥85%, `pirn/domains/data/specializations/` at ≥75%, domain library files containing pure library delegation at exempt (excluded from gating). The decision must specify how thresholds are stored and compared — config file, CI environment variable, or hardcoded in the workflow.

**3. Whether to use mutmut or switch to cosmic-ray**

mutmut is simpler to configure and already installed. cosmic-ray is more configurable (operator selection, module-level filtering, hypothesis integration) but requires more setup and has a different result database format. The tradeoff: mutmut is sufficient if the filtering problem can be solved via `paths_to_mutate` exclusions in `pyproject.toml`; cosmic-ray is preferable if operator-level control (e.g. exclude boundary-value mutations in numerical code) is needed. The decision should be made after a scoped mutmut run on `pirn/core/` to assess whether the survivor noise rate is acceptable.

**4. How to handle the abstract interface files and pure-delegation files**

Options: (a) add them to a `paths_to_exclude` list in `[tool.mutmut]`; (b) mark them with a module-level comment that signals the filter config; (c) accept the surviving mutants and document them as known noise in a `mutmut-known-survivors.txt` baseline file. Option (a) is the cleanest but requires maintaining the exclusion list. Option (c) is the most auditable.

---

## Decision

TBD — document decisions here when the sprint is planned.

---

## Consequences

TBD.
