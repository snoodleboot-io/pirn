"""YAML pipeline loader.

Steps:
1. Parse YAML into a dict.
2. Validate against ``PipelineSpec`` (Pydantic).
3. Topologically resolve node specs into knots, registering with the
   given tapestry.

Strict mode (default): any ``callable``, ``selector``, ``predicate``,
``combine``, or ``each`` reference must be supplied via the
``known_callables`` map passed to ``load_pipeline``.

Loose mode (``PipelineSpec.allow_callable_refs=True``): same references
may be dotted paths that the loader imports at load time.

The loader returns the populated ``Tapestry``; the caller picks
terminals and runs.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any

import yaml

from pirn.core.config import ErrorPolicy, KnotConfig
from pirn.core.knot import Knot, KnotFactory
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.branch import Branch
from pirn.nodes.gate import Gate
from pirn.nodes.map_ import Map
from pirn.nodes.reduce_ import Reduce
from pirn.tapestry import Tapestry
from pirn.yaml_loader.spec import (
    AggregatorSpec,
    BranchSpec,
    GateSpec,
    KnotSpec,
    MapSpec,
    ParameterSpec,
    PipelineSpec,
    ReduceSpec,
    SinkSpec,
    SourceSpec,
)


def load_pipeline(
    yaml_text: str,
    *,
    tapestry: Tapestry | None = None,
    known_callables: Mapping[str, Any] | None = None,
) -> Tapestry:
    """Load a YAML pipeline into a tapestry.

    Parameters
    ----------
    yaml_text:
        The YAML source.
    tapestry:
        Tapestry to populate.  If None, a new one is constructed.
    known_callables:
        Map of name -> callable, used in strict mode.  YAML references
        the names; the loader looks them up here.
    """
    raw = yaml.safe_load(yaml_text)
    if not isinstance(raw, dict):
        raise ValueError(
            "YAML pipeline must be a mapping at the top level"
        )
    spec = PipelineSpec.model_validate(raw)

    tapestry = tapestry or Tapestry()
    known = dict(known_callables or {})

    # Topologically order specs so each is built only after its parents.
    ordered = _topo_order_specs(spec)

    built: dict[str, Knot] = {}
    for node_spec in ordered:
        knot = _build_node(node_spec, built, spec, known, tapestry)
        if knot is not None:
            built[node_spec.id] = knot

    return tapestry


def _topo_order_specs(spec: PipelineSpec) -> list[Any]:
    """Return node specs in dependency order."""
    by_id = spec.nodes_by_id

    # Build dependency edges: child id -> [parent ids]
    deps: dict[str, list[str]] = {}
    for n in spec.nodes:
        ds: list[str] = []
        if isinstance(n, (KnotSpec, SinkSpec)):
            ds.extend(n.parents.values())
        elif isinstance(n, AggregatorSpec):
            ds.extend(n.parents.values())
        elif isinstance(n, BranchSpec):
            ds.append(n.input)
        elif isinstance(n, GateSpec):
            ds.append(n.input)
        elif isinstance(n, MapSpec):
            ds.append(n.over)
            for v in n.shared.values():
                if isinstance(v, str) and v in by_id:
                    ds.append(v)
        elif isinstance(n, ReduceSpec):
            ds.append(n.of)
        deps[n.id] = ds

    # Kahn's algorithm.
    in_degree = {nid: 0 for nid in by_id}
    children: dict[str, list[str]] = {nid: [] for nid in by_id}
    for child, parents in deps.items():
        for p in parents:
            if p not in by_id:
                raise ValueError(
                    f"node {child!r} references unknown parent {p!r}"
                )
            in_degree[child] += 1
            children[p].append(child)

    ready = sorted(nid for nid, d in in_degree.items() if d == 0)
    out: list[Any] = []
    while ready:
        nid = ready.pop(0)
        out.append(by_id[nid])
        new_ready: list[str] = []
        for c in children[nid]:
            in_degree[c] -= 1
            if in_degree[c] == 0:
                new_ready.append(c)
        ready = sorted(ready + new_ready)
    if len(out) != len(by_id):
        raise ValueError("cycle in YAML pipeline definition")
    return out


def _build_node(
    node_spec: Any,
    built: dict[str, Knot],
    pipeline_spec: PipelineSpec,
    known: dict[str, Any],
    tapestry: Tapestry,
) -> Knot | None:
    cfg = KnotConfig(
        id=node_spec.id,
        validate_io=node_spec.validate_io,
        error_policy=ErrorPolicy(node_spec.error_policy),
        description=node_spec.description,
        tags=tuple(node_spec.tags),
    )

    if isinstance(node_spec, ParameterSpec):
        type_ = _resolve_type(node_spec.type_)
        kwargs: dict[str, Any] = {
            "name": node_spec.id.split(":", 1)[-1] if ":" in node_spec.id else node_spec.id,
            "type_": type_,
            "tapestry": tapestry,
            "_config": cfg,
        }
        if node_spec.has_default:
            kwargs["default"] = node_spec.default
        return Parameter(**kwargs)

    if isinstance(node_spec, SourceSpec):
        # A source's callable is wrapped to produce no-arg process().
        callable_obj = _resolve_callable(
            node_spec.callable, known, pipeline_spec.allow_callable_refs
        )
        # Dynamically build a Source subclass whose process is the callable.
        from pirn.nodes.source import Source

        async def proc(self) -> Any:
            res = callable_obj()
            if hasattr(res, "__await__"):
                return await res
            return res

        cls = type(
            f"Source_{node_spec.id}",
            (Source,),
            {"process": proc, "__module__": __name__},
        )
        return cls(_config=cfg, tapestry=tapestry)

    if isinstance(node_spec, (KnotSpec, SinkSpec)):
        callable_obj = _resolve_callable(
            node_spec.callable, known, pipeline_spec.allow_callable_refs
        )
        # Build kwargs: parents (resolved from built) + config values.
        kwargs: dict[str, Any] = {"_config": cfg, "tapestry": tapestry}
        for input_name, parent_id in node_spec.parents.items():
            kwargs[input_name] = built[parent_id]
        for input_name, value in node_spec.config.items():
            kwargs[input_name] = value
        # Three cases:
        # (1) callable_obj is a Knot class -> instantiate.
        # (2) callable_obj is a KnotFactory (from @knot) -> call it.
        # (3) callable_obj is a plain function -> wrap with @knot first.
        if isinstance(callable_obj, type) and issubclass(callable_obj, Knot):
            return callable_obj(**kwargs)
        if isinstance(callable_obj, KnotFactory):
            return callable_obj(**kwargs)
        # Plain function — wrap with @knot.
        from pirn.core.knot import knot as _knot_decorator

        factory = _knot_decorator(callable_obj)
        return factory(**kwargs)

    if isinstance(node_spec, AggregatorSpec):
        combine = _resolve_callable(
            node_spec.combine, known, pipeline_spec.allow_callable_refs
        )
        kwargs = {
            "combine": combine,
            "_config": cfg,
            "tapestry": tapestry,
        }
        for input_name, parent_id in node_spec.parents.items():
            kwargs[input_name] = built[parent_id]
        return Aggregator(**kwargs)

    if isinstance(node_spec, BranchSpec):
        selector = _resolve_callable(
            node_spec.selector, known, pipeline_spec.allow_callable_refs
        )
        return Branch(
            input=built[node_spec.input],
            selector=selector,
            branches=tuple(node_spec.branches),
            _config=cfg,
            tapestry=tapestry,
        )

    if isinstance(node_spec, GateSpec):
        predicate = _resolve_callable(
            node_spec.predicate, known, pipeline_spec.allow_callable_refs
        )
        return Gate(
            input=built[node_spec.input],
            predicate=predicate,
            _config=cfg,
            tapestry=tapestry,
        )

    if isinstance(node_spec, MapSpec):
        each = _resolve_callable(
            node_spec.each, known, pipeline_spec.allow_callable_refs
        )
        # Resolve shared kwargs that reference other knots (loose-mode
        # ergonomics: a value matching a built knot id becomes that knot).
        shared: dict[str, Any] = {}
        for k, v in node_spec.shared.items():
            if isinstance(v, str) and v in built:
                shared[k] = built[v]
            else:
                shared[k] = v
        return Map(
            over=built[node_spec.over],
            each=each,
            bind=node_spec.bind,
            _config=cfg,
            tapestry=tapestry,
            **shared,
        )

    if isinstance(node_spec, ReduceSpec):
        combine = _resolve_callable(
            node_spec.combine, known, pipeline_spec.allow_callable_refs
        )
        kwargs = {
            "of": built[node_spec.of],
            "combine": combine,
            "_config": cfg,
            "tapestry": tapestry,
        }
        if node_spec.has_initial:
            kwargs["initial"] = node_spec.initial
        return Reduce(**kwargs)

    raise TypeError(f"unknown node spec type: {type(node_spec).__name__}")


def _resolve_callable(
    ref: str,
    known: dict[str, Any],
    allow_imports: bool,
) -> Callable[..., Any]:
    """Resolve a string reference to a callable.

    Strict order:
    1. If ``ref`` is in ``known``, return it.
    2. Otherwise, if ``allow_imports`` is True and ``ref`` looks like a
       dotted path, import and return.
    3. Otherwise, raise.
    """
    if ref in known:
        obj = known[ref]
        if not callable(obj) and not (
            isinstance(obj, type) and issubclass(obj, Knot)
        ):
            raise TypeError(
                f"known_callables[{ref!r}] is not callable"
            )
        return obj

    if not allow_imports:
        raise ValueError(
            f"reference {ref!r} not in known_callables; set "
            f"allow_callable_refs=True to enable dotted-path imports"
        )

    if "." not in ref:
        raise ValueError(
            f"reference {ref!r} is not a dotted path and not in "
            f"known_callables"
        )

    module_path, _, attr = ref.rpartition(".")
    module = importlib.import_module(module_path)
    obj = getattr(module, attr)
    if not callable(obj) and not (
        isinstance(obj, type) and issubclass(obj, Knot)
    ):
        raise TypeError(f"resolved {ref!r} is not callable")
    return obj


def _resolve_type(ref: str) -> Any:
    """Resolve a type reference (e.g. 'int', 'str', 'list[dict]') to
    a Python type usable by Pydantic TypeAdapter."""
    builtins_map = {
        "int": int,
        "str": str,
        "float": float,
        "bool": bool,
        "bytes": bytes,
        "dict": dict,
        "list": list,
        "tuple": tuple,
        "set": set,
        "Any": Any,
    }
    if ref in builtins_map:
        return builtins_map[ref]
    # Generic forms: "list[dict]", etc.
    if "[" in ref and ref.endswith("]"):
        outer, inner = ref.split("[", 1)
        inner = inner[:-1]  # strip trailing ]
        outer_t = builtins_map.get(outer)
        if outer_t is None:
            outer_t = _import_dotted(outer)
        inner_t = _resolve_type(inner)
        return outer_t[inner_t]
    return _import_dotted(ref)


def _import_dotted(ref: str) -> Any:
    if "." not in ref:
        raise ValueError(f"cannot resolve type {ref!r}")
    module_path, _, attr = ref.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, attr)
