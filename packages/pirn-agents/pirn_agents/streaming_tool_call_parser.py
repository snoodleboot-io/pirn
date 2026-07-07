"""Incremental, provider-neutral parser for streamed tool calls.

Providers stream a tool call as a series of *deltas*: small fragments that
each carry a slice of the arguments-JSON string plus, on the first fragment
for a call, its id and name. :class:`StreamingToolCallParser` accumulates
those fragments per call index and emits a
:class:`pirn_agents.types.tool_call.ToolCall` *the instant* a call is
complete — before the underlying stream finishes — so a downstream executor
(e.g. :class:`pirn_agents.parallel_tool_executor.ParallelToolExecutor`) can
begin dispatching while later calls are still arriving.

The parser is deliberately provider-agnostic: it consumes a NEUTRAL delta
shape, never a provider-specific payload. Translating a provider's native
streaming events into this neutral shape is the job of an adapter, mirroring
the philosophy of :mod:`pirn_agents.tool_call_codec`.

Neutral delta shape
--------------------
Each delta is a ``Mapping[str, Any]`` with the keys:

* ``index`` (:class:`int`) — which tool call the fragment belongs to;
  parallel calls carry distinct indices.
* ``id`` (:class:`str` | ``None``) — the call id; typically on the first
  fragment for an index. Later non-``None`` values overwrite earlier ones.
* ``name`` (:class:`str` | ``None``) — the tool name; typically on the first
  fragment for an index.
* ``arguments`` (:class:`str`) — a *fragment* of the arguments-JSON string;
  fragments for the same index are concatenated in arrival order.
* ``done`` (:class:`bool`, optional, default ``False``) — signals the
  index's call is complete.

Completion & malformed tails
----------------------------
A call is complete when a delta carries ``done=True`` for its index or,
as a fallback, when its accumulated arguments already parse as valid JSON and
a *new* index begins. On completion the accumulated arguments are parsed with
:func:`json.loads` (an empty string becomes ``{}``) and a ``ToolCall`` is
yielded immediately. If, at stream end, an index's accumulated arguments are
not valid JSON (a partial or malformed tail), the parser drops that call
rather than raising or emitting a broken value; the number of drops is
exposed via :attr:`dropped_partial` for observability.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterable, AsyncIterator, Mapping
from typing import Any

from pirn_agents.types.tool_call import ToolCall


class StreamingToolCallParser:
    """Assemble streamed argument fragments into ``ToolCall``s eagerly."""

    def __init__(self) -> None:
        """Create a parser with an empty dropped-partial counter."""
        self._dropped_partial: int = 0

    @property
    def dropped_partial(self) -> int:
        """Number of calls dropped because their tail never parsed as JSON."""
        return self._dropped_partial

    async def parse(
        self, deltas: AsyncIterable[Mapping[str, Any]]
    ) -> AsyncIterator[ToolCall]:
        """Yield each ``ToolCall`` as soon as its index is complete.

        Args:
            deltas: An async iterable of neutral delta mappings (see the
                module docstring for the shape).

        Yields:
            One :class:`ToolCall` per completed index, in completion order.
            An index whose accumulated arguments never become valid JSON is
            skipped (and counted in :attr:`dropped_partial`) rather than
            raising.
        """
        self._dropped_partial = 0
        ids: dict[int, str | None] = {}
        names: dict[int, str | None] = {}
        args: dict[int, str] = {}
        order: list[int] = []
        emitted: set[int] = set()

        async for delta in deltas:
            index = int(delta["index"])
            if index not in args:
                # A brand-new index begins: opportunistically flush any prior
                # pending index whose arguments already form valid JSON.
                for prior in order:
                    if prior in emitted:
                        continue
                    call = self._build(prior, ids, names, args)
                    if call is not None:
                        emitted.add(prior)
                        yield call
                ids[index] = None
                names[index] = None
                args[index] = ""
                order.append(index)

            delta_id = delta.get("id")
            if delta_id is not None:
                ids[index] = str(delta_id)
            delta_name = delta.get("name")
            if delta_name is not None:
                names[index] = str(delta_name)
            args[index] = args[index] + str(delta.get("arguments", ""))

            if bool(delta.get("done", False)) and index not in emitted:
                call = self._build(index, ids, names, args)
                if call is not None:
                    emitted.add(index)
                    yield call
                else:
                    emitted.add(index)
                    self._dropped_partial += 1

        # Flush any indices that completed without an explicit ``done`` and
        # were not swept up by the new-index fallback above.
        for index in order:
            if index in emitted:
                continue
            call = self._build(index, ids, names, args)
            if call is not None:
                yield call
            else:
                self._dropped_partial += 1

    async def parse_to_list(
        self, deltas: AsyncIterable[Mapping[str, Any]]
    ) -> list[ToolCall]:
        """Drain :meth:`parse` into a list, preserving emission order.

        Args:
            deltas: An async iterable of neutral delta mappings.

        Returns:
            Every :class:`ToolCall` the parser emits, in completion order.
        """
        return [call async for call in self.parse(deltas)]

    def _build(
        self,
        index: int,
        ids: dict[int, str | None],
        names: dict[int, str | None],
        args: dict[int, str],
    ) -> ToolCall | None:
        """Build a ``ToolCall`` for ``index``, or ``None`` if args are bad.

        Args:
            index: The call index to assemble.
            ids: Per-index call ids accumulated so far.
            names: Per-index tool names accumulated so far.
            args: Per-index concatenated argument-JSON fragments.

        Returns:
            A :class:`ToolCall` when the accumulated arguments are valid JSON
            (an empty string parses to ``{}``); ``None`` when the tail is
            partial or malformed, so the caller can skip it without raising.
        """
        raw_args = args[index]
        if raw_args == "":
            parsed: Any = {}
        else:
            try:
                parsed = json.loads(raw_args)
            except json.JSONDecodeError:
                return None
        if not isinstance(parsed, Mapping):
            return None
        return ToolCall(
            tool_name=str(names[index] or ""),
            arguments=parsed,
            call_id=str(ids[index] or ""),
            raw={"index": index},
        )
