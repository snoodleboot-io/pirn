"""``Tool`` — a capability the model may call, expressed as a ``Knot`` class.

A tool is three things core already names (ADR "agents speaks core", 2026-09-13,
target model item 1):

* the **capability** is the ``Tool`` *class* — what a model may be offered;
* one **call** is an *instance*, built with ``KnotConfig(id=call_id)`` and the
  call's arguments as its inputs, exactly like any other knot;
* the **outcome** is the engine's ``Ok | Err | Skipped`` plus the ``KnotLineage``
  row the run records for it.

What the agents layer adds on top is only the model-facing envelope:
:meth:`declaration` renders the class's ``name`` / ``description`` / JSON
``parameters`` for a provider, derived from the same ``process()`` type hints
core validates with (``Knot.input_json_schema``), and the capability facets a
planner or an approval policy read (:attr:`permissions`,
:meth:`requires_approval`, :attr:`streaming`).  There is no second execution
verb: ``process()`` **is** how a tool runs.

Authoring a tool is authoring a knot::

    class Calculator(Tool):
        \"\"\"Evaluate an arithmetic expression.\"\"\"

        tool_name: ClassVar[str] = "calculator"

        def __init__(self, *, expression: Knot | str, _config: KnotConfig, **kwargs: Any) -> None:
            super().__init__(expression=expression, _config=_config, **kwargs)

        async def process(self, expression: str, **_: Any) -> float:
            return evaluate(expression)

    Calculator.declaration()          # name/description/parameters for the model
    Calculator(expression="1 + 1", _config=KnotConfig(id="call_1"))   # one call

Dependencies a call does not supply — a filesystem root, a database
connector, a memory store — are ordinary inputs bound once with
:meth:`bind`, which returns a :class:`~pirn_agents.tools.tool_factory.ToolFactory`
whose declaration hides them from the model.  A
:class:`~pirn_agents.tools.toolset.Toolset` holds those factories (or bare
classes), and executing a :class:`~pirn_agents.tools.tool_call.ToolCall` is
``factory.for_call(call)`` — a knot the engine schedules, validates, retries
and times out through ``KnotConfig``.
"""

from __future__ import annotations

import contextlib
import inspect
import re
import time
from collections.abc import AsyncIterator, Generator, Mapping
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.ok import Ok
from pirn.core.result import Result

from pirn_agents.observability.agent_call_recorder import AgentCallRecorder
from pirn_agents.tools.tool_declaration import ToolDeclaration
from pirn_agents.tools.tool_error_record import ToolErrorRecord
from pirn_agents.tools.tool_permissions import ToolPermissions

if TYPE_CHECKING:
    from pirn_agents.tools.tool_factory import ToolFactory


class Tool(Knot):
    """A model-callable capability; subclass and implement ``process()``.

    Class attributes (all optional):
        tool_name: The name the model addresses the tool by.  Empty (the
            default) means the snake_case of the class name.
        tool_description: What the model is told the tool does.  Defaults to
            the first paragraph of the class docstring.
        permissions: :class:`ToolPermissions` metadata (scope, mutating,
            approval, cost hint).  Inert by default.
        streaming: Whether :meth:`stream` yields incremental output.  A
            streaming tool's ``process()`` still returns the drained value.
    """

    tool_name: ClassVar[str] = ""
    tool_description: ClassVar[str | None] = None
    #: Set by a container that reports the call itself (``ToolInvocation``),
    #: so one call yields one ``"tool"`` event, attributed to the container.
    _call_reported_by_container: ClassVar[ContextVar[bool]] = ContextVar(
        "_call_reported_by_container", default=False
    )
    permissions: ClassVar[ToolPermissions] = ToolPermissions()
    streaming: ClassVar[bool] = False

    # ``process`` below is declared in the gradual parameter form; see
    # ``Knot._dynamic_process_signature`` for why (PIR-833).
    _dynamic_process_signature: ClassVar[bool] = True

    _snake_case_re: ClassVar[re.Pattern[str]] = re.compile(r"(?<!^)(?=[A-Z])")

    async def process(self, *args: Any, **_: Any) -> Any:
        """Execute one call.  Subclasses name their inputs and return the tool's value.

        Raises:
            NotImplementedError: Always; subclasses must override this method.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")

    async def __call__(self, parent_results: Mapping[str, Any]) -> Result[Any]:
        """Run as any knot; a failed call's record is credential-scrubbed on the way out.

        A tool's failure message routinely names what it was talking to — a
        DSN, a server URL — and the engine's ``traceback_filter`` reaches only
        the traceback, never ``message``.  Scrubbing here, on the knot itself,
        keeps the guarantee every invocation path used to make individually.

        The call is also reported through
        :class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`
        (ADR WS4a) as a ``"tool"`` event under this knot's id — the call id —
        with the scrubbed message as ``detail`` on failure, so every tool call
        the engine runs (a fan-out, a ``ToolInvocation``, ``run_call``) is
        observable on the run's emitters without a hook.  A ``Skipped`` outcome
        is not a call and is not reported, and a container that reports the
        call itself (``ToolInvocation``, attributing it to the outer run)
        claims the report through :meth:`container_reports_call`.
        """
        start = time.perf_counter()
        result = await super().__call__(parent_results)
        latency = time.perf_counter() - start
        if isinstance(result, Err):
            result = Err(record=ToolErrorRecord.scrubbed_record(result.record))
            await self._record_call(ok=False, latency=latency, detail=result.record.message)
        elif isinstance(result, Ok):
            await self._record_call(ok=True, latency=latency)
        return result

    @staticmethod
    @contextlib.contextmanager
    def container_reports_call() -> Generator[None, None, None]:
        """Within the block, a container (``ToolInvocation``) reports the call itself.

        A tool knot run inside the block emits no ``"tool"`` event of its own,
        so one call yields one event, attributed to the container.
        """
        token = Tool._call_reported_by_container.set(True)
        try:
            yield
        finally:
            Tool._call_reported_by_container.reset(token)

    @staticmethod
    def call_reported_by_container() -> bool:
        """Whether a container is reporting the current call (see :meth:`container_reports_call`)."""
        return Tool._call_reported_by_container.get()

    async def _record_call(self, *, ok: bool, latency: float, detail: str | None = None) -> None:
        """Emit this call's outcome as one ``"tool"`` event (a no-op outside a run)."""
        if Tool.call_reported_by_container():
            return
        await AgentCallRecorder.record(
            knot_id=self.knot_id,
            kind="tool",
            ok=ok,
            latency=latency,
            detail=detail,
            tool_name=self.declared_name(),
            call_id=self.knot_id,
        )

    # ------------------------------------------------------------ knot introspection
    #
    # A capability wraps *any* knot class (``ToolFactory``, ``AgentTool``), and
    # reading its input contract means reading the knot machinery core keeps
    # for ``Knot`` subclasses. ``Tool`` is the agents layer's ``Knot`` subclass,
    # so the wrappers ask it rather than reaching into ``Knot`` themselves.

    @staticmethod
    def framework_kwarg_names() -> frozenset[str]:
        """The construction kwargs core reserves for the framework (``_config``, ``tapestry``)."""
        return Knot.reserved_kwargs()

    @staticmethod
    def declared_input_schema(knot_class: type[Knot]) -> Mapping[str, Any] | None:
        """The JSON schema declaring ``knot_class``'s inputs, or ``None`` when its signature does."""
        return knot_class._input_schema_override

    @staticmethod
    def input_annotations(knot_class: type[Knot]) -> dict[str, Any]:
        """Name -> the annotation core validates each signature-declared ``process()`` input with."""
        signature = inspect.signature(knot_class.process)
        return knot_class._input_annotations(signature, knot_class._process_hints(signature))

    # ------------------------------------------------------------ envelope

    @classmethod
    def declared_name(cls) -> str:
        """The name the model addresses this tool by."""
        if cls.tool_name:
            return cls.tool_name
        return cls._snake_case_re.sub("_", cls.__name__).lower()

    @classmethod
    def declared_description(cls) -> str:
        """The description shown to the model."""
        if cls.tool_description is not None:
            return cls.tool_description
        own_doc = cls.__dict__.get("__doc__")
        doc = inspect.cleandoc(own_doc) if isinstance(own_doc, str) else ""
        first = doc.split("\n\n")[0].strip()
        return first or cls.declared_name()

    @classmethod
    def declaration(cls) -> ToolDeclaration:
        """Return the provider-neutral declaration of this capability.

        ``parameters`` is ``Knot.input_json_schema()`` — the same hints
        ``validate_io`` checks — with Knot-typed and ``PirnOpaqueValue``-typed
        inputs already excluded by core (a live resource is wired, never
        supplied by a model).  Bind dependencies with :meth:`bind` to hide
        them too.
        """
        return cls.factory().declaration()

    @classmethod
    def factory(cls) -> ToolFactory:
        """This class as a :class:`ToolFactory` with nothing bound."""
        from pirn_agents.tools.tool_factory import ToolFactory  # local: avoids a cycle

        return ToolFactory(cls)

    @classmethod
    def bind(cls, **config: Any) -> ToolFactory:
        """Bind inputs a call never supplies and return the resulting factory.

        ``ReadFileTool.bind(root="/srv")`` is the read-file capability scoped
        to ``/srv``: its declaration hides ``root``, and every call it
        constructs carries it.
        """
        return cls.factory().bind(**config)

    @classmethod
    def requires_approval(cls) -> bool:
        """Whether a call must be approved by a human (from :attr:`permissions`)."""
        return cls.permissions.approval_required

    @classmethod
    def stream(cls, arguments: Mapping[str, Any]) -> AsyncIterator[Any]:
        """Return an async iterator of partial results for ``arguments``.

        Default: raise :class:`TypeError` — a non-streaming tool has nothing
        to stream.  A streaming subclass sets ``streaming = True`` and
        overrides this; its ``process()`` returns the drained chunks.
        """
        raise TypeError(f"tool {cls.declared_name()!r} is not a streaming tool")

    @classmethod
    async def collect_stream(cls, arguments: Mapping[str, Any]) -> list[Any]:
        """Drain :meth:`stream` for ``arguments`` into a list of chunks."""
        return [chunk async for chunk in cls.stream(arguments)]

    def _clear_credentials(self) -> None:
        """Drop any in-memory credential reference held by the tool.

        A knot-shaped tool holds its dependencies as bound inputs, so there
        is nothing to clear by default; a subclass holding a live secret on
        a ``_mutable_`` slot overrides this.
        """
        return None

    def __repr__(self) -> str:
        return f"<{type(self).__name__} call={self.knot_id!r}>"
