"""The DeepSeek agent.

Stateless by design: every call is one system message (byte-stable for the whole session,
so DeepSeek's automatic prefix cache hits it) plus one user message (the briefing, which
carries all of this agent's memory). There is no conversation history and no tool loop.

Every call — turn, broadcast reply, post-trade note, year-end note — reasons, and carries
the same private memory. Both were once cut back for cost and both failed measurement;
see docs/design-deltas.md §5.
"""

from __future__ import annotations

from ..config import AgentSpec, Rules
from ..llm import get_provider
from ..llm.base import Usage
from ..prompts import (broadcast_system_prompt, build_brief, build_broadcast_brief,
                       coerce_broadcast, coerce_turn, reflect_system_prompt, system_prompt,
                       validate)
from .base import (Agent, BroadcastContext, BroadcastDecision, NO_QUOTE, TurnContext,
                   TurnDecision)


def _envelope(r: dict, *, system: str, user: str) -> dict:
    """The model exchange, flattened for the ``model_turn`` event. Prompts are stored in
    full: reconstructing a decision post hoc must not require re-rendering anything.

    ``reasoning`` is the chain of thought. It is the primary evidence for §11.3 — whether
    an uninformed agent actually inferred the state from price or merely landed on the
    right number — and the one-word ``basis`` self-report cannot substitute for it. Audience
    only: it is written with agent_visible=false and is never fed back to a model.
    """
    return {
        "system": system,
        "user": user,
        "completion": r.get("text", ""),
        "reasoning": r.get("reasoning", ""),
        "error": r.get("error"),
        "api_error": bool(r.get("api_error")),
        "retries": r.get("retries", 0),
        "backoff_s": r.get("backoff_s", 0.0),
        "repairs": r.get("repairs", 0),
        "latency_s": round(r.get("latency_s", 0.0), 3),
        "usage": r["usage"].to_dict() if r.get("usage") else {},
    }


class LLMAgent(Agent):
    kind = "llm"

    def __init__(self, seat: str, spec: AgentSpec, rules: Rules, market,
                 name: str | None = None) -> None:
        super().__init__(seat)
        self.spec = spec
        self.rules = rules
        self.mkt = market
        self.provider = get_provider(
            model=spec.model, temperature=spec.temperature,
            max_output_tokens=spec.max_output_tokens, max_retries=spec.max_retries,
            pace=spec.pace, thinking=spec.thinking, reasoning_effort=spec.reasoning_effort,
            repair_retries=spec.repair_retries, base_url=spec.base_url,
            api_key_env=spec.api_key_env)
        # Built once; identical bytes on every call for this seat.
        self.system = system_prompt(seat, rules, market, name)
        self.broadcast_system = broadcast_system_prompt(seat, rules, market, name)
        self.reflect_system = reflect_system_prompt(seat, rules, market, name)
        self._schema_kind = "turn" if rules.elicit_beliefs else "turn_no_beliefs"

    # ------------------------------------------------------------------ turn

    def decide_turn(self, ctx: TurnContext) -> TurnDecision:
        user = build_brief(
            market=self.mkt, seat=ctx.seat, period=ctx.period, round_no=ctx.round_no, turn_seq=ctx.turn_seq,
            info=ctx.info, card=ctx.card, certs=ctx.certs, cash=ctx.cash, book=ctx.book,
            market_log=ctx.market_log, reflections=ctx.reflections, history=ctx.history,
            not_selected=ctx.not_selected, names=ctx.names, rules=self.rules)
        # The cap is passed explicitly even though the provider was constructed with the
        # same number, so all three channels state their budget at the call site. The
        # channel that did NOT was broadcast, and it ran on the provider default for the
        # project's whole life while the scenarios said 512.
        r = self.provider.complete_json(self.system, user, thinking=self.spec.thinking,
                                        max_output_tokens=self.spec.max_output_tokens)
        env = _envelope(r, system=self.system, user=user)

        data = r.get("data")
        if data is None:
            env["schema_errors"] = ["no parseable json"]
            return TurnDecision(action=NO_QUOTE, malformed=True, raw=env)

        data = coerce_turn(data, elicit_beliefs=self.rules.elicit_beliefs,
                           states=tuple(self.mkt.states))
        errors = validate(self._schema_kind, data, tuple(self.mkt.states))
        if errors:
            env["schema_errors"] = errors
            # A malformed belief block should not throw away a well-formed action. Only
            # treat the reply as lost — and record a violation — when the ACTION itself
            # fails to validate.
            if validate("turn_no_beliefs", {"action": data.get("action")}):
                return TurnDecision(action=NO_QUOTE, malformed=True, raw=env)

        act = data.get("action") or {}
        return TurnDecision(
            action=act.get("type", NO_QUOTE),
            side=act.get("side"),
            price=act.get("price"),
            posterior=data.get("posterior"),
            reservation_buy=data.get("reservation_buy"),
            reservation_sell=data.get("reservation_sell"),
            basis=data.get("basis"),
            raw=env,
        )

    # ------------------------------------------------------------------ broadcast

    def respond_broadcast(self, ctx: BroadcastContext) -> BroadcastDecision:
        user = build_broadcast_brief(
            market=self.mkt, seat=ctx.seat, period=ctx.period, quote=ctx.quote, info=ctx.info, card=ctx.card,
            certs=ctx.certs, cash=ctx.cash, book=ctx.book, market_log=ctx.market_log,
            reflections=ctx.reflections, history=ctx.history,
            not_selected=ctx.not_selected, names=ctx.names, rules=self.rules)
        # `broadcast_max_output_tokens` was never passed here, so every broadcast in every
        # run so far used the provider default of 8192 and the setting did nothing. It
        # matters: broadcasts are ~70% of all calls, and on a locally served Qwen3.6 they
        # came back at a median of 1,830 output tokens against a configured cap of 512.
        r = self.provider.complete_json(
            self.broadcast_system, user,
            thinking=self.spec.broadcast_thinking,
            max_output_tokens=self.spec.broadcast_max_output_tokens)
        env = _envelope(r, system=self.broadcast_system, user=user)

        data = r.get("data")
        if data is None:
            env["schema_errors"] = ["no parseable json"]
            return BroadcastDecision(response="decline", malformed=True, raw=env)

        data = coerce_broadcast(data)
        errors = validate("broadcast", data)
        if errors:
            env["schema_errors"] = errors
            return BroadcastDecision(response="decline", malformed=True, raw=env)
        return BroadcastDecision(response=data["response"], why=data.get("why"), raw=env)

    # ------------------------------------------------------------------ reflection

    def reflect(self, kind: str, system: str, user: str) -> dict:
        # Reflections run with thinking on by default. They used to be forced off as a cost
        # saving, and the notes came out wrong in a way that persisted: 20 of the 20 smoke
        # notes stating a prior expected value stated the naive 50/50 one. A note is
        # durable memory, so the error outlived the call that made it.
        #
        # An EMPTY answer is retried, up to spec.reflect_empty_retries times. Nothing
        # retried it before: max_retries covers transient API errors, repair_retries covers
        # unparseable JSON, and complete_text sets repairs = 0, so the text channel had no
        # loop at all — an empty note went straight to a violation and was discarded. It is
        # almost never a model with nothing to say; it is a call that spent its whole
        # output budget reasoning, which is why retrying works at all.
        sys_text = system or self.reflect_system
        usage, attempts, retries, backoff_s, latency = Usage(), 0, 0, 0.0, 0.0
        while True:
            r = self.provider.complete_text(
                sys_text, user, thinking=self.spec.reflect_thinking,
                max_output_tokens=self.spec.reflect_max_output_tokens)
            attempts += 1
            # Summed across attempts, exactly as complete_json does across its repairs, so
            # a retried reflection is billed for what it actually spent. `or Usage()`
            # because a provider may report nothing, which _envelope already guards for.
            usage += r.get("usage") or Usage()
            retries += r.get("retries", 0)
            backoff_s += r.get("backoff_s", 0.0)
            latency += r.get("latency_s", 0.0)
            text = (r.get("text") or "").strip()
            # Stop on an answer, on a real API failure (retrying THAT is max_retries' job
            # and it has already given up), or when the allowance is spent.
            if text or r.get("api_error") or attempts > self.spec.reflect_empty_retries:
                break
        r.update(usage=usage, retries=retries, backoff_s=backoff_s, latency_s=latency)
        env = _envelope(r, system=sys_text, user=user)
        # How many calls this note cost. 1 is the ordinary case; >1 means the first answer
        # came back empty, which is invisible in the log without this.
        env["attempts"] = attempts
        return {"text": text, "raw": env}

    @property
    def reflect_system_text(self) -> str:
        return self.reflect_system
