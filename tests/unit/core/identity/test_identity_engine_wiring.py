from __future__ import annotations

import asyncio
import unittest
from typing import Any
from unittest.mock import patch

from pirn.core.identity.null_identity_resolver import NullIdentityResolver
from pirn.core.identity.static_identity_resolver import StaticIdentityResolver
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry


def _make_simple_tapestry(**kwargs) -> Tapestry:
    from pirn.core.knot import Knot
    from pirn.core.knot_config import KnotConfig

    class _Leaf(Knot):
        def process(self, **_: Any) -> str:
            return "ok"

    t = Tapestry(**kwargs)
    with t:
        _Leaf(_config=KnotConfig(id="leaf"))
    return t


class TestIdentityEngineWiring(unittest.TestCase):
    def test_run_request_actor_overrides_resolver(self) -> None:
        t = _make_simple_tapestry(identity_resolver=StaticIdentityResolver("resolver-actor"))
        request = RunRequest(actor="explicit-actor")
        result = asyncio.run(t.run(request))
        self.assertEqual(result.actor, "explicit-actor")

    def test_resolver_used_when_request_actor_absent(self) -> None:
        t = _make_simple_tapestry(identity_resolver=StaticIdentityResolver("svc-ingest"))
        result = asyncio.run(t.run(RunRequest()))
        self.assertEqual(result.actor, "svc-ingest")

    def test_null_resolver_produces_none_actor(self) -> None:
        t = _make_simple_tapestry(identity_resolver=NullIdentityResolver())
        result = asyncio.run(t.run(RunRequest()))
        self.assertIsNone(result.actor)

    def test_trigger_flows_through_from_request(self) -> None:
        t = _make_simple_tapestry(identity_resolver=NullIdentityResolver())
        request = RunRequest(trigger="webhook:order-placed")
        result = asyncio.run(t.run(request))
        self.assertEqual(result.trigger, "webhook:order-placed")

    def test_trigger_none_when_not_set(self) -> None:
        t = _make_simple_tapestry(identity_resolver=NullIdentityResolver())
        result = asyncio.run(t.run(RunRequest()))
        self.assertIsNone(result.trigger)

    def test_default_resolver_uses_os_user(self) -> None:
        t = _make_simple_tapestry()
        with patch("getpass.getuser", return_value="test-os-user"):
            result = asyncio.run(t.run(RunRequest()))
        self.assertEqual(result.actor, "test-os-user")

    def test_env_var_takes_precedence_over_os_user(self) -> None:
        t = _make_simple_tapestry()
        with patch.dict("os.environ", {"GITHUB_ACTOR": "octocat"}, clear=False):
            result = asyncio.run(t.run(RunRequest()))
        self.assertEqual(result.actor, "octocat")
