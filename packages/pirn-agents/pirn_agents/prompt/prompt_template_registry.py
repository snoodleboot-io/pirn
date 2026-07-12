"""``PromptTemplateRegistry`` — a namespaced, versioned registry of templates.

Modelled on the tool registry's lookup layer: templates register under a
``(namespace, name, version)`` key and resolve in **O(1)** by that key, or by
``(namespace, name)`` with automatic resolution to the newest version. Unlike
the tool registry this holds a single concrete type (:class:`PromptTemplate`),
so it does *not* mirror into the shared ``sweet_tea`` registry — the lookup is
purely local instance storage.

Versions compare as dotted numeric tuples (``"1.10.0" > "1.9.0"``) with a
lexical fallback for non-numeric labels.
"""

from __future__ import annotations

from pirn_agents.prompt.prompt_template import PromptTemplate


def _version_key(version: str) -> tuple[tuple[int, str], ...]:
    """Return a sortable key for a dotted ``version`` string."""
    parts: list[tuple[int, str]] = []
    for part in version.split("."):
        if part.isdigit():
            parts.append((int(part), ""))
        else:
            parts.append((-1, part))
    return tuple(parts)


class PromptTemplateRegistry:
    """A registry of prompt templates keyed by namespace, name, and version."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._by_key: dict[tuple[str, str, str], PromptTemplate] = {}
        self._versions: dict[tuple[str, str], list[str]] = {}

    def register(self, template: PromptTemplate, *, namespace: str = "default") -> None:
        """Register ``template`` under ``(namespace, name, version)``.

        The template's own ``name``/``version`` form the key, so authoring a new
        version is simply registering another :class:`PromptTemplate`.

        Raises
        ------
        TypeError
            If ``template`` is not a :class:`PromptTemplate`.
        ValueError
            If the ``(namespace, name, version)`` key is already registered.
        """
        if not isinstance(template, PromptTemplate):
            raise TypeError(f"template must be a PromptTemplate, got {type(template).__name__}")
        key = (namespace, template.name, template.version)
        if key in self._by_key:
            raise ValueError(
                f"template already registered: namespace={namespace!r} "
                f"name={template.name!r} version={template.version!r}"
            )
        self._by_key[key] = template
        versions = self._versions.setdefault((namespace, template.name), [])
        versions.append(template.version)
        versions.sort(key=_version_key)

    def get(
        self, name: str, *, namespace: str = "default", version: str | None = None
    ) -> PromptTemplate | None:
        """Return a registered template, or ``None`` when no match exists.

        With ``version`` given the lookup is an exact O(1) key hit; without it
        the newest registered version in ``namespace`` is resolved.
        """
        if version is not None:
            return self._by_key.get((namespace, name, version))
        latest = self.latest_version(name, namespace=namespace)
        if latest is None:
            return None
        return self._by_key.get((namespace, name, latest))

    def unregister(self, name: str, *, namespace: str = "default", version: str) -> bool:
        """Remove one ``(namespace, name, version)`` entry.

        Returns ``True`` when an entry was removed, ``False`` when no such key
        was registered.
        """
        key = (namespace, name, version)
        if key not in self._by_key:
            return False
        del self._by_key[key]
        versions = self._versions.get((namespace, name))
        if versions is not None and version in versions:
            versions.remove(version)
            if not versions:
                del self._versions[(namespace, name)]
        return True

    def latest_version(self, name: str, *, namespace: str = "default") -> str | None:
        """Return the highest registered version of ``name``, or ``None``."""
        versions = self._versions.get((namespace, name))
        if not versions:
            return None
        return versions[-1]

    def versions(self, name: str, *, namespace: str = "default") -> list[str]:
        """Return all registered versions of ``name``, lowest first."""
        return list(self._versions.get((namespace, name), []))

    def names(self, *, namespace: str = "default") -> list[str]:
        """Return the sorted template names registered in ``namespace``."""
        return sorted({n for ns, n in self._versions if ns == namespace})

    def namespaces(self) -> list[str]:
        """Return the sorted list of namespaces holding at least one template."""
        return sorted({namespace for namespace, _, _ in self._by_key})

    def __len__(self) -> int:
        """Return the number of registered ``(namespace, name, version)`` entries."""
        return len(self._by_key)

    def __contains__(self, key: object) -> bool:
        """Return whether a ``(namespace, name, version)`` tuple is registered."""
        return key in self._by_key
