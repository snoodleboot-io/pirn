from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.skipped import Skipped


class BranchOutput(Knot):
    """One output of a ``Branch``.

    Internal: produced by ``Branch.__init__``; users access them via
    ``branch[name]`` and wire them as parents of downstream knots.

    The output is Ok(input_value) if this branch was selected, otherwise
    Skipped.

    Algorithm:
        1. Construction — each ``BranchOutput`` is wired with two parents:
           ``chosen`` (the owning ``Branch``, whose output is the selected
           branch name) and ``passthrough`` (the ``Branch``'s own ``input``
           parent, so the original value reaches here without going through
           ``Branch.process()``, which only returns the selected name).
        2. Resolution — the engine resolves both parents and passes them to
           ``process()``.
        3. Match — if ``chosen`` equals this output's own ``branch_name``,
           ``passthrough`` is returned unchanged.
        4. No match — otherwise ``process()`` returns
           ``Skipped(reason="branch_not_selected")``, which ``Knot.__call__``
           passes through bare, so downstream knots wired to the
           non-selected outputs are skipped rather than failed.
    """

    def __init__(
        self,
        *,
        source: Knot,
        branch_name: str,
        _config: KnotConfig,
        tapestry: Any = None,
    ) -> None:
        self._mutable_branch_name = branch_name

        original_input = source.parents["input"]
        self._bootstrap(
            config=_config,
            parents={"chosen": source, "passthrough": original_input},
            tapestry=tapestry,
        )

        self._frozen = True

    async def process(self, chosen: str, passthrough: Any, **_: Any) -> Any:
        """Return the passthrough value if this branch was selected, else declare the skip.

        Args:
            chosen: Branch name selected by the upstream Branch knot.
            passthrough: Original input value forwarded from the Branch's input knot.

        Returns:
            The passthrough value when this branch's name matches the chosen
            branch, otherwise ``Skipped(reason="branch_not_selected")``.
        """
        if chosen == self._mutable_branch_name:
            return passthrough
        return Skipped(
            reason="branch_not_selected",
            detail={"branch_name": self._mutable_branch_name},
        )
