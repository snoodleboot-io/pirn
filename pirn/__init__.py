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

import warnings
from importlib.metadata import PackageNotFoundError, version

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SweetTeaWarning)
    Registry.fill_registry()

try:
    __version__ = version("pirn")
except PackageNotFoundError:
    __version__ = "unknown"

# Public API re-exports — users may import from pirn directly.
# Registry.fill_registry() above must run first; noqa: E402 suppresses the
# "import not at top of file" warnings that follow from that ordering.
from pirn.core.assembler import Assembler
from pirn.core.disassembler import Disassembler
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.sink import Sink
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

__all__ = [
    "Tapestry",
    "Knot",
    "KnotConfig",
    "knot",
    "Parameter",
    "RunRequest",
    "RunResult",
    "ErrorPolicy",
    "Assembler",
    "Disassembler",
    "Sink",
    "Source",
    "SubTapestry",
    "LoopSubTapestry",
]
