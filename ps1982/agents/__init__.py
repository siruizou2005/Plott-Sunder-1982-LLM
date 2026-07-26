from __future__ import annotations

import numpy as np

from ..config import AgentSpec, Rules
from .base import (ACCEPT_STANDING, Agent, BroadcastContext, BroadcastDecision,  # noqa: F401
                   NO_QUOTE, QUOTE, TurnContext, TurnDecision)
from .llm_agent import LLMAgent  # noqa: F401
from .scripted import BOT_REGISTRY, PIAgent, REAgent, ZIAgent  # noqa: F401


def build_agent(seat: str, spec: AgentSpec, rules: Rules, rng: np.random.Generator,
                market, name: str | None = None) -> Agent:
    if spec.kind == "llm":
        return LLMAgent(seat, spec, rules, market, name)
    return BOT_REGISTRY[spec.kind](seat, rng, market)
