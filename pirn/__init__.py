"""pirn — a pipeline framework where everything is a knot.

Knot discovery
--------------
At import time, pirn calls :meth:`sweet_tea.registry.Registry.fill_registry`
over its own package tree. Every :class:`pirn.core.knot.Knot` subclass shipped
with pirn is auto-registered under ``library="pirn"`` with the lowercase
class name as its registry key (CamelCase, snake_case, and no-underscore
variations all resolve to the same entry through sweet_tea's
:meth:`BaseFactory._generate_key_variations`).

This means YAML pipelines can reference any built-in pirn knot by name
without ``import`` boilerplate::

    nodes:
      - id: read
        callable: object_store_read_source

User projects: register your own knots
--------------------------------------
If you define your own :class:`Knot` subclasses outside the pirn package
(e.g. ``my_company.transforms.NormaliseAddresses``), call
:meth:`Registry.fill_registry` from **your** project's package init so your
classes are auto-discovered too::

    # my_company/__init__.py
    from sweet_tea.registry import Registry

    Registry.fill_registry()  # scans my_company/ and registers every class

After that, your knots are resolvable by name from YAML pipelines just like
pirn's built-ins. To restrict YAML resolution to your library only, pass
``library="my_company"`` to :class:`pirn.yaml_loader.knot_resolver.KnotResolver`
when building the loader.
"""
from sweet_tea.registry import Registry

Registry.fill_registry()
