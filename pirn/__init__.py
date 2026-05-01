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

YAML name resolution goes through
:class:`sweet_tea.abstract_inverter_factory.AbstractInverterFactory[Knot]`
— sweet_tea's typed factory that returns the class definition (rather than
instantiating it), so the loader can supply construction kwargs later.

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
pirn's built-ins. To restrict resolution to your library only, look up via
``AbstractInverterFactory[Knot].create(name, library="my_company")``.
"""
from sweet_tea.registry import Registry

Registry.fill_registry()
