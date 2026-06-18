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

Import allowlist (``allowed_module_prefixes``): when loose mode is
enabled, the optional ``allowed_module_prefixes`` parameter (accepted by
both ``load_pipeline`` and ``PipelineSpec``) restricts which module
paths may be imported.  A callable ref is permitted only when its module
path equals one of the prefixes or starts with ``<prefix>.``.  When the
list is ``None``, any import is allowed (with a warning).  The spec-
level list and the caller-supplied list are merged: both must grant
access (i.e. the effective allowlist is the intersection; if either
source supplies ``None`` the other source's list is used as-is).

The loader returns the populated ``Tapestry``; the caller picks
terminals and runs.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any

import yaml

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory, knot
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.branch.branch import Branch
from pirn.nodes.gate.gate import Gate
from pirn.nodes.map_markers import Map
from pirn.nodes.reduce_ import Reduce
from pirn.tapestry import Tapestry
from pirn.yaml_loader.specs.aggregator_spec import AggregatorSpec
from pirn.yaml_loader.specs.branch_spec import BranchSpec
from pirn.yaml_loader.specs.gate_spec import GateSpec
from pirn.yaml_loader.specs.knot_spec import KnotSpec
from pirn.yaml_loader.specs.map_spec import MapSpec
from pirn.yaml_loader.specs.pipeline_spec import PipelineSpec
from pirn.yaml_loader.specs.reduce_spec import ReduceSpec
from pirn.yaml_loader.specs.sink_spec import SinkSpec
from pirn.yaml_loader.specs.source_spec import SourceSpec
from pirn.yaml_loader.specs.yaml_parameter_spec import YamlParameterSpec


class PipelineLoader:
    """Load a YAML pipeline definition into a :class:`Tapestry`.

    The loader is stateless; instances exist only as a hook for
    extension. Use :meth:`load` to parse, validate, and materialise
    a YAML pipeline.
    """

    def load(
        self,
        yaml_text: str,
        *,
        tapestry: Tapestry | None = None,
        known_callables: Mapping[str, Any] | None = None,
        allowed_module_prefixes: list[str] | None = None,
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
        allowed_module_prefixes:
            When ``allow_callable_refs=True``, only callable refs whose
            module path equals one of these prefixes or starts with
            ``<prefix>.`` may be imported.  ``None`` means no restriction
            from the caller side (the spec-level list still applies).
        """
        raw = yaml.safe_load(yaml_text)
        if not isinstance(raw, dict):
            raise ValueError("YAML pipeline must be a mapping at the top level")
        spec = PipelineSpec.model_validate(raw)

        tapestry = tapestry or Tapestry()
        known = dict(known_callables or {})

        # Merge caller-supplied and spec-level allowlists.
        # If both are non-None, use the intersection (union of restrictions).
        # If only one is non-None, use that one.
        effective_prefixes: list[str] | None
        if allowed_module_prefixes is not None and spec.allowed_module_prefixes is not None:
            spec_set = set(spec.allowed_module_prefixes)
            effective_prefixes = [p for p in allowed_module_prefixes if p in spec_set]
        elif allowed_module_prefixes is not None:
            effective_prefixes = allowed_module_prefixes
        else:
            effective_prefixes = spec.allowed_module_prefixes

        # Topologically order specs so each is built only after its parents.
        ordered = self._topo_order_specs(spec)

        built: dict[str, Knot] = {}
        for node_spec in ordered:
            built_knot = self._build_node(
                node_spec, built, spec, known, tapestry, effective_prefixes
            )
            if built_knot is not None:
                built[node_spec.id] = built_knot

        return tapestry

    @staticmethod
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
                    raise ValueError(f"node {child!r} references unknown parent {p!r}")
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

    @staticmethod
    def _build_node(
        node_spec: Any,
        built: dict[str, Knot],
        pipeline_spec: PipelineSpec,
        known: dict[str, Any],
        tapestry: Tapestry,
        allowed_module_prefixes: list[str] | None = None,
    ) -> Knot | None:
        cfg = KnotConfig(
            id=node_spec.id,
            validate_io=node_spec.validate_io,
            error_policy=ErrorPolicy(node_spec.error_policy),
            description=node_spec.description,
            tags=tuple(node_spec.tags),
        )

        if isinstance(node_spec, YamlParameterSpec):
            type_ = PipelineLoader._resolve_type(node_spec.type_)
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
            callable_obj = PipelineLoader._resolve_callable(
                node_spec.callable,
                known,
                pipeline_spec.allow_callable_refs,
                allowed_module_prefixes,
            )
            if isinstance(callable_obj, KnotFactory):
                factory = callable_obj
            elif isinstance(callable_obj, type) and issubclass(callable_obj, Knot):
                return callable_obj(_config=cfg, tapestry=tapestry)
            else:
                factory = knot(callable_obj)
            return factory(_config=cfg, tapestry=tapestry)

        if isinstance(node_spec, (KnotSpec, SinkSpec)):
            callable_obj = PipelineLoader._resolve_callable(
                node_spec.callable,
                known,
                pipeline_spec.allow_callable_refs,
                allowed_module_prefixes,
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
            from pirn.core.knot_factory import knot as _knot_decorator

            factory = _knot_decorator(callable_obj)
            return factory(**kwargs)

        if isinstance(node_spec, AggregatorSpec):
            combine = PipelineLoader._resolve_callable(
                node_spec.combine, known, pipeline_spec.allow_callable_refs, allowed_module_prefixes
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
            selector = PipelineLoader._resolve_callable(
                node_spec.selector,
                known,
                pipeline_spec.allow_callable_refs,
                allowed_module_prefixes,
            )
            return Branch(
                input=built[node_spec.input],
                selector=selector,
                branches=tuple(node_spec.branches),
                _config=cfg,
                tapestry=tapestry,
            )

        if isinstance(node_spec, GateSpec):
            predicate = PipelineLoader._resolve_callable(
                node_spec.predicate,
                known,
                pipeline_spec.allow_callable_refs,
                allowed_module_prefixes,
            )
            return Gate(
                input=built[node_spec.input],
                predicate=predicate,
                _config=cfg,
                tapestry=tapestry,
            )

        if isinstance(node_spec, MapSpec):
            each = PipelineLoader._resolve_callable(
                node_spec.each, known, pipeline_spec.allow_callable_refs, allowed_module_prefixes
            )
            # Resolve shared kwargs; string values matching a built knot id become
            # that knot (loose-mode ergonomics).
            shared: dict[str, Any] = {}
            for k, v in node_spec.shared.items():
                if isinstance(v, str) and v in built:
                    shared[k] = built[v]
                else:
                    shared[k] = v
            # Translate old `type: map` YAML into the new annotation-based API:
            # each(bind_name=Map(over_knot), **shared, _config=cfg, tapestry=tapestry)
            return each(
                **{node_spec.bind: Map(built[node_spec.over])},
                **shared,
                _config=cfg,
                tapestry=tapestry,
            )

        if isinstance(node_spec, ReduceSpec):
            combine = PipelineLoader._resolve_callable(
                node_spec.combine, known, pipeline_spec.allow_callable_refs, allowed_module_prefixes
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

    @staticmethod
    def _resolve_callable(
        ref: str,
        known: dict[str, Any],
        allow_imports: bool,
        allowed_module_prefixes: list[str] | None = None,
    ) -> Callable[..., Any]:
        """Resolve a string reference to a callable.

        Resolution order (first match wins):
        1. ``known`` dict — per-call overrides, highest priority.
        2. ``AbstractInverterFactory[Knot]`` — sweet_tea typed lookup over the
           global registry, populated by ``Registry.fill_registry()`` at package
           import time. Returns the class definition (lazy construction; the
           loader supplies kwargs later).
        3. Dotted-path import — only when ``allow_callable_refs=True``.
        """
        if ref in known:
            obj = known[ref]
            if not callable(obj) and not (isinstance(obj, type) and issubclass(obj, Knot)):
                raise TypeError(f"known_callables[{ref!r}] is not callable")
            return obj

        from sweet_tea.abstract_inverter_factory import AbstractInverterFactory
        from sweet_tea.sweet_tea_error import SweetTeaError

        try:
            return AbstractInverterFactory[Knot].create(ref)
        except SweetTeaError:
            # Not registered as a Knot — fall through to dotted-path resolution.
            pass

        if not allow_imports:
            raise ValueError(
                f"reference {ref!r} not in known_callables and not registered as a Knot "
                "in sweet_tea's Registry; if it belongs to a pirn domain, install & "
                "import the owning package (e.g. pip install pirn-<x> then "
                "import pirn_<x>, or call pirn.discover_installed_domains()); "
                "otherwise set allow_callable_refs=True to enable dotted-path imports, "
                "or call Registry.fill_registry() in your project so your knots are "
                "auto-discovered"
            )

        if "." not in ref:
            raise ValueError(f"reference {ref!r} is not a dotted path and not in known_callables")

        module_path, _, attr = ref.rpartition(".")

        if allowed_module_prefixes is not None:
            if not any(
                module_path == p or module_path.startswith(p + ".") for p in allowed_module_prefixes
            ):
                raise ValueError(
                    f"callable ref {ref!r} resolves to module {module_path!r} which is not in "
                    f"allowed_module_prefixes {allowed_module_prefixes!r}; "
                    f"set allow_callable_refs=True and add the module prefix to "
                    f"allowed_module_prefixes to permit this import"
                )

        module = importlib.import_module(module_path)
        obj = getattr(module, attr)
        if not callable(obj) and not (isinstance(obj, type) and issubclass(obj, Knot)):
            raise TypeError(f"resolved {ref!r} is not callable")
        return obj

    @staticmethod
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
                outer_t = PipelineLoader._import_dotted(outer)
            inner_t = PipelineLoader._resolve_type(inner)
            return outer_t[inner_t]
        return PipelineLoader._import_dotted(ref)

    @staticmethod
    def _import_dotted(ref: str) -> Any:
        if "." not in ref:
            raise ValueError(f"cannot resolve type {ref!r}")
        module_path, _, attr = ref.rpartition(".")
        module = importlib.import_module(module_path)
        return getattr(module, attr)


def load_pipeline(
    yaml_text: str,
    *,
    tapestry: Tapestry | None = None,
    known_callables: Mapping[str, Any] | None = None,
    allowed_module_prefixes: list[str] | None = None,
) -> Tapestry:
    """Backwards-compatible wrapper around :meth:`PipelineLoader.load`."""
    return PipelineLoader().load(
        yaml_text,
        tapestry=tapestry,
        known_callables=known_callables,
        allowed_module_prefixes=allowed_module_prefixes,
    )
