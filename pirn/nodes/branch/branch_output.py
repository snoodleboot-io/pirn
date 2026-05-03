from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.branch._branch_not_selected import _BranchNotSelected


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
        source: Knot,
        branch_name: str,
        _config: KnotConfig,
        tapestry: Any = None,
    ) -> None:
        self._mutable_branch_name = branch_name

        self._mutable_config = _config
        original_input = source.parents["input"]
        self._mutable_parents = {
            "chosen": source,
            "passthrough": original_input,
        }
        self._mutable_config_values = {}
        self._mutable_input_adapters = {}
        self._mutable_output_adapter = None
        self._mutable_mapped_inputs: dict = {}

        from pirn.tapestry import _CURRENT_TAPESTRY

        target = tapestry or _CURRENT_TAPESTRY.get(None)
        if target is not None:
            target.register(self)

        self._frozen = True

    async def process(self, chosen: str, passthrough: Any, **_: Any) -> Any:  # type: ignore[override]
        """Return the passthrough value if this branch was selected, or raise to signal it was not.

        Args:
            chosen: Branch name selected by the upstream Branch knot.
            passthrough: Original input value forwarded from the Branch's input knot.

        Returns:
            The passthrough value when this branch's name matches the chosen branch.

        Raises:
            _BranchNotSelected: If this branch was not the one selected; converted to Skipped by ``__call__``.
        """
        if chosen == self._mutable_branch_name:
            return passthrough
        raise _BranchNotSelected(self._mutable_branch_name)

    async def __call__(self, parent_results: Any) -> Any:
        from pirn.core.err import Err as _Err
        from pirn.core.skipped import Skipped as _Skipped

        result = await super().__call__(parent_results)
        if isinstance(result, _Err) and result.record.exc_type == "_BranchNotSelected":
            return _Skipped(
                reason="branch_not_selected",
                detail={"branch_name": self._mutable_branch_name},
            )
        return result
