"""Branch — route a value to one of N named paths.

A ``Branch`` takes one input and a selector function that returns the
name of the chosen path.  Each branch is exposed as a ``BranchOutput``
knot that downstream knots can wire to as a parent.

Only the selected branch's output is ``Ok``; the others are ``Skipped``
with reason "branch_not_selected".  This lets downstream knots use
their normal ``error_policy`` to react.

Example::

    def classify(payload: dict) -> str:
        return "tool_call" if payload.get("type") == "tool" else "response"

    with Tapestry() as t:
        payload = ...
        branch = Branch(
            input=payload,
            selector=classify,
            branches=("tool_call", "response"),
            _config=KnotConfig(id="route"),
        )
        # Wire downstream knots to specific branches:
        handle_tool(payload=branch["tool_call"], ...)
        handle_response(payload=branch["response"], ...)

If ``classify`` returns a name not in ``branches``, every branch output
is ``Skipped`` and a synthetic Err is recorded against the Branch knot.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.config import KnotConfig
from pirn.core.knot import Knot


class Branch(Knot):
    """Selector-based router."""

    def __init__(
        self,
        *,
        input: Knot,
        selector: Callable[[Any], str],
        branches: tuple[str, ...],
        _config: KnotConfig | None = None,
        tapestry: Any = None,
    ) -> None:
        if not isinstance(input, Knot):
            raise TypeError("Branch: 'input' must be a Knot")
        if not callable(selector):
            raise TypeError("Branch: 'selector' must be callable")
        if not branches:
            raise TypeError("Branch requires at least one branch name")
        if len(set(branches)) != len(branches):
            raise TypeError("Branch: duplicate branch names")
        if _config is None:
            raise TypeError("Branch requires _config=KnotConfig(id=...)")

        self._mutable_selector = selector
        self._mutable_branch_names = branches

        self._mutable_config = _config
        self._mutable_parents = {"input": input}
        self._mutable_config_values = {}
        self._mutable_input_adapters = {}
        self._mutable_output_adapter = None

        from pirn.tapestry import _CURRENT_TAPESTRY

        target = tapestry or _CURRENT_TAPESTRY.get(None)
        if target is not None:
            target.register(self)

        # Pre-build the BranchOutput sub-knots.  Each is a real Knot in
        # the tapestry; downstream wiring uses them as parents.  We
        # construct them after registering the Branch itself so the
        # tapestry sees the outputs in a sensible order.
        self._mutable_outputs: dict[str, BranchOutput] = {}
        for name in branches:
            out = BranchOutput(
                _config=KnotConfig(id=f"{_config.id}/{name}"),
                source=self,
                branch_name=name,
                tapestry=target,
            )
            self._mutable_outputs[name] = out

        self._frozen = True

    def __getitem__(self, branch_name: str) -> BranchOutput:
        try:
            return self._mutable_outputs[branch_name]
        except KeyError as exc:
            raise KeyError(
                f"Branch {self.knot_id!r} has no branch {branch_name!r}; "
                f"available: {list(self._mutable_outputs)}"
            ) from exc

    @property
    def branch_names(self) -> tuple[str, ...]:
        return self._mutable_branch_names

    async def process(self, input: Any) -> str:
        # Apply the selector.  Returns the chosen branch name, which the
        # BranchOutput sub-knots compare against their own name to
        # decide Ok-vs-Skipped.  We also produce the input value as the
        # output payload, packaged with the chosen name so the
        # BranchOutput knots can pass through the value.
        chosen = self._mutable_selector(input)
        if chosen not in self._mutable_branch_names:
            raise RuntimeError(
                f"Branch {self.knot_id!r}: selector returned {chosen!r}, "
                f"not in declared branches {self._mutable_branch_names!r}"
            )
        return chosen


class BranchOutput(Knot):
    """One output of a ``Branch``.

    Internal: produced by ``Branch.__init__``; users access them via
    ``branch[name]`` and wire them as parents of downstream knots.

    The output is Ok(input_value) if this branch was selected, otherwise
    Skipped.
    """

    def __init__(
        self,
        *,
        source: Branch,
        branch_name: str,
        _config: KnotConfig,
        tapestry: Any = None,
    ) -> None:
        if not isinstance(source, Branch):
            raise TypeError("BranchOutput: source must be a Branch")

        self._mutable_branch_name = branch_name

        self._mutable_config = _config
        # Two parents: the Branch (gives chosen name) and the original
        # input (so we can pass the value through).  The original input
        # is reachable via source.parents["input"].
        original_input = source.parents["input"]
        self._mutable_parents = {
            "chosen": source,
            "passthrough": original_input,
        }
        self._mutable_config_values = {}
        self._mutable_input_adapters = {}
        self._mutable_output_adapter = None

        from pirn.tapestry import _CURRENT_TAPESTRY

        target = tapestry or _CURRENT_TAPESTRY.get(None)
        if target is not None:
            target.register(self)

        self._frozen = True

    async def process(self, chosen: str, passthrough: Any) -> Any:
        if chosen == self._mutable_branch_name:
            return passthrough
        # Signal to the engine to treat this as Skipped rather than Ok.
        # We do this by raising a sentinel; the engine catches all
        # exceptions and produces Err — which isn't what we want here.
        # Instead we'll rely on a custom mechanism: BranchOutput returns
        # a tagged sentinel, and we override __call__ to convert it.
        raise _BranchNotSelected(self._mutable_branch_name)

    async def __call__(self, parent_results: Any) -> Any:
        # Override Knot.__call__ to convert _BranchNotSelected into Skipped.
        from pirn.core.result import Skipped as _Skipped

        result = await super().__call__(parent_results)
        from pirn.core.result import Err as _Err

        if isinstance(result, _Err) and result.record.exc_type == "_BranchNotSelected":
            return _Skipped(
                reason="branch_not_selected",
                detail={"branch_name": self._mutable_branch_name},
            )
        return result


class _BranchNotSelected(Exception):
    """Internal sentinel raised by BranchOutput.process when its branch
    was not the one selected.  Caught and converted to Skipped by the
    BranchOutput's __call__ override."""
