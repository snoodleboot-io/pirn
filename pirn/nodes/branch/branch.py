"""Branch — route a value to one of N named paths.

A ``Branch`` takes one input and a selector function that returns the
name of the chosen path.  Each branch is exposed as a ``BranchOutput``
knot that downstream knots can wire to as a parent.

Only the selected branch's output is ``Ok``; the others are ``Skipped``
with reason "branch_not_selected".
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.branch.branch_output import BranchOutput


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
        self._mutable_mapped_inputs: dict = {}

        from pirn.tapestry import _CURRENT_TAPESTRY

        target = tapestry or _CURRENT_TAPESTRY.get(None)
        if target is not None:
            target.register(self)

        self._mutable_outputs: dict[str, BranchOutput] = {}
        for name in branches:
            out = BranchOutput(
                _config=KnotConfig(id=f"{_config.id}:{name}"),
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

    async def process(self, input: Any, **_: Any) -> str:  # type: ignore[override]
        """Apply the selector to the input value and return the name of the chosen branch.

        Args:
            input: Value produced by the upstream knot, forwarded unchanged to the selector.

        Returns:
            Name of the branch selected by the selector callable.

        Raises:
            RuntimeError: If the selector returns a name not in the declared branches tuple.
        """
        chosen = self._mutable_selector(input)
        if chosen not in self._mutable_branch_names:
            raise RuntimeError(
                f"Branch {self.knot_id!r}: selector returned {chosen!r}, "
                f"not in declared branches {self._mutable_branch_names!r}"
            )
        return chosen
