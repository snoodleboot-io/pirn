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
from pirn.core.run_context_vars import RunContextVars
from pirn.exceptions.invalid_branch_error import InvalidBranchError
from pirn.nodes.branch.branch_output import BranchOutput


class Branch(Knot):
    """Selector-based router that directs one input to exactly one of N named paths.

    A ``Branch`` takes one parent knot and a ``selector`` callable that maps
    the input value to a branch name.  For each declared branch name a
    companion ``BranchOutput`` knot is created and registered in the same
    tapestry.  Downstream knots wire to individual ``BranchOutput`` knots
    (accessed via ``branch["name"]``) rather than to the ``Branch`` itself.

    Algorithm:
        1. Construction — for every name in ``branches``, a ``BranchOutput``
           knot with ID ``{branch_id}:{name}`` is created and registered in the
           tapestry.  Each ``BranchOutput`` holds a reference to this ``Branch``
           and its own branch name.
        2. Resolution — the engine resolves the single parent and passes its
           output to ``Branch.process()``.
        3. Selection — ``process()`` calls ``selector(input)`` to obtain the
           chosen branch name.  If the returned name is not in
           ``branch_names``, an ``InvalidBranchError`` is raised.
        4. Branch output dispatch — the engine calls each ``BranchOutput.process``
           with the ``Branch``'s output (the selected name).  Each
           ``BranchOutput`` compares its own name to the selected name:
           matching outputs return the original input value wrapped in ``Ok``;
           non-matching outputs return ``Skipped(reason="branch_not_selected")``.
        5. Downstream propagation — knots downstream of a non-selected
           ``BranchOutput`` receive ``Skipped`` and are themselves skipped,
           so only the chosen execution path continues.
    """

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

        self._mutable_execution_extra: dict[str, Any] = {}

        self._bootstrap(
            config=_config,
            parents={"input": input},
            config_values={"selector": selector, "branch_names": branches},
            tapestry=tapestry,
        )

        target = tapestry or RunContextVars.tapestry.get(None)

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

    def branch_names(self) -> tuple[str, ...]:
        """Return the declared branch names, in construction order."""
        return self._mutable_config_values["branch_names"]

    def lineage_extra(self) -> dict[str, Any]:
        return {**super().lineage_extra(), **self._mutable_execution_extra}

    async def __call__(self, parent_results: Any) -> Any:
        from pirn.core.ok import Ok as _Ok

        result = await super().__call__(parent_results)
        if isinstance(result, _Ok):
            self._mutable_execution_extra = {"selected_branch": result.value}
        return result

    async def process(
        self,
        input: Any,
        selector: Callable[[Any], str],
        branch_names: tuple[str, ...],
        **_: Any,
    ) -> str:  # type: ignore[override]
        """Apply the selector to the input value and return the name of the chosen branch.

        Args:
            input: Value produced by the upstream knot, forwarded unchanged to the selector.
            selector: Callable that maps the input value to a branch name.
            branch_names: The declared branch names the selector must choose among.

        Returns:
            Name of the branch selected by the selector callable.

        Raises:
            InvalidBranchError: If the selector returns a name not in the declared branches tuple.
        """
        chosen = selector(input)
        if chosen not in branch_names:
            raise InvalidBranchError(
                f"Branch {self.knot_id!r}: selector returned {chosen!r}, "
                f"not in declared branches {branch_names!r}"
            )
        return chosen
