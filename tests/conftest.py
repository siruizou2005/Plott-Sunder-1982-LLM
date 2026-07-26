"""Shared fixtures. The whole suite is OFFLINE: no test may reach the network.

``StubAgent`` replaces the LLM agent with a scripted reply queue, so the engine's turn
loop, matching and settlement can be driven deterministically.
"""

from __future__ import annotations

import pytest

from ps1982.agents.base import (Agent, BroadcastContext, BroadcastDecision, NO_QUOTE,
                                TurnContext, TurnDecision)
from ps1982.config import Config
from ps1982.engine import Engine
from ps1982.events import EventStream, ListSink


class StubAgent(Agent):
    """Replays a fixed script. ``turns`` is a list of TurnDecision; ``accepts`` decides
    every broadcast response."""

    kind = "stub"

    def __init__(self, seat: str, turns=None, accepts: bool = False) -> None:
        super().__init__(seat)
        self.turns = list(turns or [])
        self.accepts = accepts
        self.briefs: list[TurnContext] = []

    def decide_turn(self, ctx: TurnContext) -> TurnDecision:
        self.briefs.append(ctx)
        if self.turns:
            return self.turns.pop(0)
        return TurnDecision(action=NO_QUOTE)

    def respond_broadcast(self, ctx: BroadcastContext) -> BroadcastDecision:
        return BroadcastDecision(response="accept" if self.accepts else "decline")


@pytest.fixture
def engine_factory():
    """Build an Engine whose agents are stubs, and hand back (engine, sink, agents)."""

    def make(agents: dict[str, Agent] | None = None, **cfg_kwargs):
        cfg = Config(**{"run_name": "test", "sessions": 1, **cfg_kwargs})
        sink = ListSink()
        stream = EventStream(sink)
        eng = Engine(cfg, stream)
        if agents:
            eng.agents.update(agents)
        for seat, a in eng.agents.items():
            if not isinstance(a, StubAgent) and (agents is None or seat not in agents):
                eng.agents[seat] = StubAgent(seat)
        return eng, sink, eng.agents

    return make
