"""Provider-neutral mapping between pirn tool-calling types and providers.

:class:`ToolCallCodec` orchestrates the round-trip of native tool calling
without embedding any provider-specific knowledge. It converts a
:class:`pirn_agents.tools.toolset.Toolset` into native tool declarations, decodes
a provider's assistant message into :class:`pirn_agents.tools.tool_call.ToolCall`
values, and encodes each call's outcome — the engine's ``Ok | Err | Skipped``
recorded under the call's id, with its ``KnotLineage`` row — back into native
tool-result messages (ADR agents-speaks-core, WS1).

Every provider-specific decision — the exact JSON shape of a tool
declaration, where tool calls live inside an assistant message, how a
tool result is framed — is delegated to a
:class:`pirn_agents.llm.provider_adapter.ProviderAdapter`. Swapping providers
means swapping adapters; this module never changes and imports nothing
provider-specific. The only cross-provider convention it owns is that
"arguments-as-JSON" may arrive either as a JSON string or as an already
parsed mapping, handled with the stdlib :mod:`json` module.

The codec is opaque to pydantic (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
identity serialiser keeps content-addressing stable.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.err import Err
from pirn.core.knot_lineage import KnotLineage
from pirn.core.ok import Ok
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.result import Result
from pirn.core.run_result import RunResult
from pirn.core.skipped import Skipped

from pirn_agents.llm.provider_adapter import ProviderAdapter
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.toolset import Toolset


class ToolCallCodec(PirnOpaqueValue):
    """Provider-neutral codec for native tool calling via an adapter."""

    def __init__(self, adapter: ProviderAdapter) -> None:
        """Bind the codec to the ``adapter`` doing provider-specific shaping.

        Args:
            adapter: The :class:`ProviderAdapter` that translates neutral
                shapes to and from one provider's native tool-calling JSON.
        """
        self._adapter: ProviderAdapter = adapter

    def encode_tools(self, toolset: Toolset) -> list[Any]:
        """Adapt a toolset's neutral schema into native tool declarations.

        Args:
            toolset: The tools to declare to the provider.

        Returns:
            One provider-native tool declaration per registered tool, in
            registration order.
        """
        return [self._adapter.tool_to_native(neutral) for neutral in toolset.schema()]

    def decode_calls(self, provider_msg: Any) -> list[ToolCall]:
        """Decode a provider assistant message into neutral tool calls.

        Handles single and parallel tool calls uniformly, and accepts
        arguments as either a JSON string or an already parsed mapping.

        Args:
            provider_msg: A provider-native assistant message.

        Returns:
            One :class:`ToolCall` per tool call, preserving order and the
            provider-native ``raw`` dict each was decoded from.
        """
        return [
            ToolCall(
                tool_name=raw["name"],
                arguments=self._parse_arguments(raw["arguments"]),
                call_id=raw["id"],
                raw=raw,
            )
            for raw in self._adapter.extract_tool_calls(provider_msg)
        ]

    def encode_results(
        self,
        results: Sequence[ToolResult] | Mapping[str, Result[Any]],
        *,
        lineage: Sequence[KnotLineage] = (),
    ) -> list[Any]:
        """Encode each call's outcome into a native tool-result message.

        Args:
            results: Either ``{call_id: Ok | Err | Skipped}`` — the engine's
                outcome for each call knot, keyed by the call's id — or, for
                one deprecation cycle, a sequence of :class:`ToolResult` views.
            lineage: The run's lineage rows; the row recorded under a call's
                knot id supplies its latency to the view.  Optional.

        Returns:
            One provider-native tool-result message per result, in order.  The
            neutral content is the error string for an ``Err`` (``"<type>:
            <message>"``), ``"call skipped: <reason>"`` for a ``Skipped``
            (PIR-865: rendered through :meth:`ToolResult.from_result`, whose
            view carries :attr:`~pirn_agents.tools.tool_status.ToolStatus.SKIPPED`
            rather than ``ERROR`` — a caller reading ``status`` rather than
            just this text still sees the call was skipped, not failed), and
            the produced value coerced to a JSON-safe form for an ``Ok``.
        """
        views = self.views(results, lineage=lineage)
        native: list[Any] = []
        for view in views:
            content = view.error if view.error is not None else self._jsonable(view.result)
            native.append(
                self._adapter.result_to_native({"call_id": view.call_id, "content": content})
            )
        return native

    @classmethod
    def views(
        cls,
        results: Sequence[ToolResult] | Mapping[str, Result[Any]],
        *,
        lineage: Sequence[KnotLineage] = (),
    ) -> list[ToolResult]:
        """The :class:`ToolResult` view of each outcome, built through ``from_result``."""
        if isinstance(results, Mapping):
            rows = {row.knot_id: row for row in lineage}
            return [
                ToolResult.from_result(call_id, result, rows.get(ToolFactory.knot_id_for(call_id)))
                for call_id, result in results.items()
            ]
        return list(results)

    @staticmethod
    def outcomes_of(run: RunResult, calls: Sequence[ToolCall]) -> dict[str, Result[Any]]:
        """Read each call's ``Ok | Err | Skipped`` back out of a finished run.

        A call ran under ``ToolFactory.knot_id_for(call.call_id)``; its value
        is in ``run.outputs``, its failure in ``run.exceptions`` (by the
        lineage row's ``error_record_id``), and a skip in ``run.skipped``.

        Args:
            run: The run the call knots executed in.
            calls: The calls to read back, in the order the results should
                come out.

        Returns:
            ``{call_id: Result}`` in the order of *calls*; a call the run does
            not know is ``Skipped(reason="not_run")``.
        """
        rows = {row.knot_id: row for row in run.lineage}
        records = {record.id: record for record in run.exceptions}
        outcomes: dict[str, Result[Any]] = {}
        for call in calls:
            knot_id = ToolFactory.knot_id_for(call.call_id)
            row = rows.get(knot_id)
            if knot_id in run.outputs:
                outcomes[call.call_id] = Ok(value=run.outputs[knot_id])
            elif row is not None and row.error_record_id in records:
                outcomes[call.call_id] = Err(record=records[row.error_record_id])
            elif row is not None and row.outcome == "skipped":
                outcomes[call.call_id] = Skipped(reason=row.skip_reason or "skipped")
            else:
                outcomes[call.call_id] = Skipped(reason="not_run")
        return outcomes

    def _parse_arguments(self, arguments: Any) -> Mapping[str, Any]:
        """Return ``arguments`` as a mapping, parsing a JSON string if given.

        Args:
            arguments: Either a JSON object string or a mapping.

        Returns:
            The arguments as a mapping; a JSON string is decoded via
            :func:`json.loads`, a mapping is returned unchanged.
        """
        if isinstance(arguments, str):
            parsed: Any = json.loads(arguments)
            return parsed
        return arguments

    def _jsonable(self, value: Any) -> Any:
        """Coerce ``value`` to a JSON-serialisable form, falling back to str.

        Args:
            value: Any tool result value.

        Returns:
            ``value`` unchanged when it survives a JSON round-trip,
            otherwise its :func:`str` rendering.
        """
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            return str(value)
        return value
