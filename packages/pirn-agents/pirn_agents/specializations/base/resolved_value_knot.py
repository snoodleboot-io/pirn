"""``ResolvedValueKnot`` — deprecated; construct a core ``Parameter`` instead.

A :class:`~pirn.nodes.sub_tapestry.SubTapestry` builds its inner graph inside
``process()``, at which point every input it declared has already been
resolved to a plain value (Rule 2, ``knot-design-rules.md``). Wiring that value
into a fan-out marker (:class:`~pirn.nodes.map_markers.Map`,
:class:`~pirn.nodes.map_markers.ZipMap`, :class:`~pirn.nodes.map_markers.DictMap`)
or an :class:`~pirn.nodes.aggregator.Aggregator` parent requires a *knot*, not a
bare value — those primitives fan out over, or wait on, a source knot.

Core already has this primitive: :class:`~pirn.core.parameter.Parameter` is a
graph-root knot whose value is a construction-time default (or a run-bound
value); this is exactly the same mechanism ``Knot._coerce_scalar_parameters``
uses internally to auto-wrap a plain scalar passed to a ``Knot | T`` field
(``pirn/core/knot.py:379``). ``ResolvedValueKnot`` re-implemented that by hand
before ``Parameter`` existed in its current form; every call site in this
package has been migrated to construct ``Parameter`` directly (see
``evaluator_optimizer_pipeline.py:109`` for the idiom), so this class now
exists only as a one-cycle deprecation shim for external callers.

No runtime ``DeprecationWarning`` is raised here (docstring-only deprecation):
Knot Design Rule 1 (``knot-design-rules.md``) requires ``__init__`` to contain
nothing but a single ``super().__init__(...)`` call, enforced by
``scripts/check_conventions.py``'s ``knot_init_impure`` rule for any class
whose name ends in ``Knot`` — which the deprecated public name must keep — and
moving a warning into ``__new__`` is not a workaround: ``Knot.run_scoped_copy``
calls ``copy.copy(self)`` on every knot before every run, which reconstructs
via ``cls.__new__(cls)`` with no arguments, so a ``__new__`` requiring
``value``/``_config`` breaks every run through this knot, not just
construction. Filed as a core-tooling gap in the ADR agents-speaks-core WS5a
report: there is currently no way to attach a per-construction
``DeprecationWarning`` to a Knot-shaped deprecation shim.

ADR: agents-speaks-core WS5a (PIR-856).

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter


class ResolvedValueKnot(Parameter):
    """Deprecated: construct :class:`pirn.core.parameter.Parameter` directly.

    Kept importable as a one-cycle deprecation shim (ADR agents-speaks-core
    WS5a) — see the module docstring for why it cannot also raise a runtime
    ``DeprecationWarning``. ``value`` must already be a plain, resolved
    value — the ``Knot`` half of the historical ``Knot | Any`` signature was
    never exercised by any in-tree caller and cannot be preserved by a
    ``Parameter``, which is a graph root with no parents; wire an upstream
    ``Knot`` directly to its real consumer instead of through this shim.
    """

    def __init__(
        self,
        *,
        value: Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            f"resolved:{_config.id}",
            Any,
            default=value,
            _config=_config,
            tapestry=kwargs.get("tapestry"),
        )
