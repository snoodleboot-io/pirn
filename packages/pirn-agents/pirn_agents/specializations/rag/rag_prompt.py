"""``RagPrompt`` — render a :class:`PromptBinding` whose text carries ``{{ slot }}``s.

Every prompt shipped under ``specializations/rag`` splices runtime values into
the *middle* of its instruction text — the retrieved passages, the route names,
the number of sub-questions to produce. Binding only the leading static run would
leave an operator able to retune half a sentence, which is not a tunable prompt.
So each binding's ``default`` here is the **whole** prompt, with every runtime
value written as a ``{{ slot }}``, and this helper fills the slots at the call
site.

The extra step exists because :meth:`PromptBinding.resolve` returns its built-in
``default`` verbatim: only a template that an operator registered in the catalog
is passed through :meth:`PromptTemplate.render`. Resolving first and rendering
once here handles both branches identically — a catalog hit comes back with its
slots still literal (the catalog renders non-strict with no variables), so the
single pass below is what fills them either way.

Rendering is non-strict for the same reason :meth:`PromptCatalog.resolve` is: a
slot an operator's override introduces that the call site cannot supply stays
literal ``{{ text }}`` in the prompt rather than raising mid-turn inside a
running agent. Substitution is a single left-to-right pass that never re-scans
what it inserts, so a retrieved passage containing ``{{ ... }}`` is inert.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.prompt.prompt_catalog import PromptCatalog
from pirn_agents.prompt.prompt_template import PromptTemplate


class RagPrompt:
    """Resolve a :class:`PromptBinding` and substitute its ``{{ slot }}`` values."""

    #: Version stamped on the throwaway template wrapping the resolved text. The
    #: binding already pinned which registered version it resolved against, so
    #: this identity is never looked up — it only satisfies ``PromptTemplate``.
    _render_version: ClassVar[str] = "1.0.0"

    @classmethod
    def render(
        cls,
        binding: PromptBinding,
        variables: Mapping[str, Any],
        *,
        catalog: PromptCatalog | None = None,
    ) -> str:
        """Return ``binding``'s prompt text with ``variables`` substituted.

        Args:
            binding: The binding declaring the built-in default and the catalog
                name an operator overrides against.
            variables: Slot values keyed by the ``{{ name }}`` used in the text.
            catalog: The catalog to resolve against; defaults to the
                process-wide :meth:`PromptCatalog.shared`.

        Returns:
            The prompt text to send, with every supplied slot filled.

        Raises:
            TypeError: If ``binding`` is not a :class:`PromptBinding`.
        """
        if not isinstance(binding, PromptBinding):
            raise TypeError(
                f"RagPrompt: binding must be a PromptBinding, got {type(binding).__name__}"
            )
        template = PromptTemplate(
            name=binding.name,
            version=cls._render_version,
            template=binding.resolve(catalog=catalog),
        )
        return template.render(variables, strict=False)
