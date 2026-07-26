"""Turn loop, matching and settlement (design doc §6-§8)."""

from __future__ import annotations

import json

from ps1982.agents.base import ACCEPT_STANDING, NO_QUOTE, QUOTE, TurnDecision
from ps1982.params import FIXED_COST, INITIAL_CASH, INITIAL_CERTS, SEATS, dividend
from tests.conftest import StubAgent


def q(side, price):
    return TurnDecision(action=QUOTE, side=side, price=price,
                        posterior={"X": 0.4, "Y": 0.6}, reservation_buy=price,
                        reservation_sell=price, basis="prior")


def _events(sink, t):
    return [e for e in sink.events if e.type == t]


# ---------------------------------------------------------------- MATCH branches


def test_match_zero_acceptors_posts_to_the_book(engine_factory):
    eng, sink, agents = engine_factory()
    agents["S01"] = StubAgent("S01", turns=[q("bid", 300)])
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    eng.run_turn("S01", 1, 1)

    assert eng.book.bid is not None and eng.book.bid.price == 300
    assert eng.market_log[-1]["outcome"] == "posted"
    b = _events(sink, "broadcast")[0].payload
    assert b["n_accept"] == 0 and b["winner"] is None
    assert len(b["recipients"]) == 11          # everyone else holds a certificate


def test_match_one_acceptor_trades(engine_factory):
    eng, sink, agents = engine_factory()
    agents["S01"] = StubAgent("S01", turns=[q("bid", 300)])
    agents["S09"] = StubAgent("S09", accepts=True)
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    eng.run_turn("S01", 1, 1)

    trades = _events(sink, "trade")
    assert len(trades) == 1
    assert trades[0].payload == {**trades[0].payload, "buyer": "S01", "seller": "S09",
                                 "price": 300, "trigger": "broadcast"}
    assert eng.book.bid is None                # an accepted quote never reaches the book
    assert eng.h("S01").certs == INITIAL_CERTS + 1
    assert eng.h("S09").cash == INITIAL_CASH + 300


def test_match_many_acceptors_picks_one_and_hides_the_losers(engine_factory):
    """§0.2: the losers' acceptances are erased from the agent-visible record but MUST be
    kept in the computer log — they are the potential demand curve."""
    eng, sink, agents = engine_factory()
    agents["S01"] = StubAgent("S01", turns=[q("bid", 300)])
    for s in ("S09", "S10", "S11"):
        agents[s] = StubAgent(s, accepts=True)
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    eng.run_turn("S01", 1, 1)

    b = _events(sink, "broadcast")[0]
    assert b.payload["n_accept"] == 3
    assert b.payload["winner"] in ("S09", "S10", "S11")
    assert len(b.payload["losers"]) == 2
    assert b.agent_visible is False            # invisible to agents, kept for analysis

    assert len(_events(sink, "trade")) == 1
    # Exactly one counterparty appears in the agent-visible market log.
    entry = eng.market_log[-1]
    assert entry["outcome"] == "traded"
    assert entry["buyer"] == "S01" and entry["seller"] == b.payload["winner"]
    for loser in b.payload["losers"]:
        assert loser not in (entry["buyer"], entry["seller"])


# ---------------------------------------------------------------- crossing


def test_crossing_settles_at_the_standing_price(engine_factory):
    """§5.3: price priority goes to whoever posted first."""
    eng, sink, agents = engine_factory()
    agents["S09"] = StubAgent("S09", turns=[q("ask", 340)])
    agents["S01"] = StubAgent("S01", turns=[q("bid", 400)])
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    eng.run_turn("S09", 1, 1)                  # posts, nobody accepts
    eng.run_turn("S01", 1, 2)                  # crosses it

    t = _events(sink, "trade")[-1].payload
    assert t["price"] == 340 and t["trigger"] == "crossed_auto"
    assert t["buyer"] == "S01" and t["seller"] == "S09"
    assert eng.book.ask is None


def test_other_side_survives_a_trade(engine_factory):
    """§5.4: only the quote that was consumed leaves; the opposite side stands."""
    eng, sink, agents = engine_factory()
    agents["S01"] = StubAgent("S01", turns=[q("bid", 200)])
    agents["S09"] = StubAgent("S09", turns=[q("ask", 340)])
    agents["S02"] = StubAgent("S02", turns=[TurnDecision(action=ACCEPT_STANDING, side="ask")])
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    eng.run_turn("S01", 1, 1)
    eng.run_turn("S09", 1, 2)
    eng.run_turn("S02", 1, 3)

    assert eng.book.ask is None                # consumed
    assert eng.book.bid is not None and eng.book.bid.price == 200   # survives


def test_superseded_quote_is_marked(engine_factory):
    eng, sink, agents = engine_factory()
    agents["S01"] = StubAgent("S01", turns=[q("bid", 300)])
    agents["S02"] = StubAgent("S02", turns=[q("bid", 310)])
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    eng.run_turn("S01", 1, 1)
    eng.run_turn("S02", 1, 2)

    outcomes = [e["outcome"] for e in eng.market_log]
    assert outcomes == ["superseded", "posted"]
    assert eng.book.bid.seat == "S02"


# ---------------------------------------------------------------- violations


def test_rejected_quote_is_invisible_to_everyone_else(engine_factory):
    """§5.2: a rejected attempt must not become an information channel."""
    eng, sink, agents = engine_factory()
    agents["S01"] = StubAgent("S01", turns=[q("bid", 300)])
    agents["S02"] = StubAgent("S02", turns=[q("bid", 250)])   # no improvement
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    eng.run_turn("S01", 1, 1)
    assert eng.run_turn("S02", 1, 2) is False

    v = _events(sink, "violation")[-1]
    assert v.payload["reason"] == "no_improvement" and v.payload["price"] == 250
    assert v.agent_visible is False
    assert len(eng.market_log) == 1            # only S01's quote is on the record


def test_accepting_your_own_quote_is_rejected(engine_factory):
    eng, sink, agents = engine_factory()
    agents["S01"] = StubAgent("S01", turns=[q("ask", 300),
                                            TurnDecision(action=ACCEPT_STANDING, side="ask")])
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    eng.run_turn("S01", 1, 1)
    assert eng.run_turn("S01", 1, 2) is False
    assert _events(sink, "violation")[-1].payload["reason"] == "illegal_accept"


def test_stale_standing_quote_fails_silently(engine_factory):
    """§5.5: a poster whose position moved can no longer honour their quote."""
    eng, sink, agents = engine_factory()
    agents["S09"] = StubAgent("S09", turns=[q("ask", 300)])
    agents["S01"] = StubAgent("S01", turns=[TurnDecision(action=ACCEPT_STANDING, side="ask")])
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    eng.run_turn("S09", 1, 1)
    eng.h("S09").certs = 0                     # sold out in the meantime
    assert eng.run_turn("S01", 1, 2) is False

    assert eng.book.ask is None
    assert _events(sink, "violation")[-1].payload["reason"] == "stale_quote"
    assert not _events(sink, "trade")


# ---------------------------------------------------------------- period / round


def test_round_stops_early_when_nobody_acts(engine_factory):
    eng, sink, _ = engine_factory(max_rounds_per_period=3)
    eng.run_period(1, "Y", "none")             # every stub returns no_quote
    assert len(_events(sink, "round_start")) == 1


def test_round_cap_is_respected(engine_factory):
    eng, sink, agents = engine_factory(max_rounds_per_period=2)
    for i, s in enumerate(SEATS):
        agents[s] = StubAgent(s, turns=[q("bid", 100 + i * 10) for _ in range(3)])
    eng.run_period(1, "Y", "none")
    assert len(_events(sink, "round_start")) == 2


def test_settlement_arithmetic(engine_factory):
    eng, sink, _ = engine_factory()
    eng.run_period(1, "X", "insider")

    pe = _events(sink, "period_end")[-1].payload
    assert pe["state"] == "X"
    for seat, r in pe["results"].items():
        # No trades happened, so everyone still holds their endowment.
        assert r["certs"] == INITIAL_CERTS
        assert r["dividend"] == INITIAL_CERTS * dividend(seat, "X")
        assert r["profit"] == INITIAL_CASH + r["dividend"] - FIXED_COST


def test_holdings_and_book_reset_each_period(engine_factory):
    eng, sink, agents = engine_factory(max_rounds_per_period=1)
    agents["S01"] = StubAgent("S01", turns=[q("bid", 300)])
    eng.run_period(1, "Y", "none")
    assert eng.book.bid is None                # cleared at period end
    eng.run_period(2, "Y", "none")
    assert eng.market_log == []
    for s in SEATS:
        assert eng.h(s).certs == INITIAL_CERTS and eng.h(s).cash == INITIAL_CASH


def test_clue_cards_by_information_condition(engine_factory):
    eng, sink, _ = engine_factory(max_rounds_per_period=1)
    eng.run_period(1, "Y", "none")
    assert all(v is None for v in eng.cards.values())      # blank cards for everyone
    eng.run_period(2, "Y", "insider")
    assert sum(v == "Y" for v in eng.cards.values()) == 6   # two of each type
    eng.run_period(3, "X", "all")
    assert all(v == "X" for v in eng.cards.values())


def test_period_start_hides_the_state_from_agents(engine_factory):
    eng, sink, _ = engine_factory(max_rounds_per_period=1)
    eng.run_period(1, "X", "insider")
    ps = _events(sink, "period_start")[-1]
    assert ps.payload["state"] == "X"
    assert ps.agent_visible is False


def test_llm_seat_gets_a_brief_event_that_renders(engine_factory):
    """The engine renders the briefing a SECOND time, purely to log it verbatim.

    Every stub agent has kind "stub", so that branch is invisible to the rest of the
    suite — it once shipped with two stale arguments and only failed against the live API.
    This drives it with an llm-kinded stub so a signature change cannot slip through again.
    """
    class LLMishStub(StubAgent):
        kind = "llm"

    eng, sink, _ = engine_factory({"S01": LLMishStub("S01")}, periods=1,
                                  max_rounds_per_period=1)
    eng.period = 1
    eng.cards = {s: None for s in eng.names}      # a no-information year
    eng.run_turn("S01", round_no=1, turn_seq=1)

    briefs = _events(sink, "brief")
    assert len(briefs) == 1 and briefs[0].seat == "S01"
    text = briefs[0].payload["text"]
    # The blocks a turn briefing must carry, and no seat id anywhere in it.
    for block in ("== YOUR POSITION ==", "== YOUR CLUE CARD THIS YEAR ==",
                  "== STANDING QUOTES ==", "== THIS YEAR'S PUBLIC RECORD ==",
                  "== YOUR RECORD SO FAR =="):
        assert block in text
    assert eng.names["S01"] in text
    for s in eng.names:
        assert s not in text


def test_empty_reflection_is_recorded_not_swallowed(engine_factory):
    """Reasoning shares the output budget, so a note can come back empty having spent the
    lot thinking. Six of twelve year-end notes were lost that way on the probe run, with
    nothing in the log to show for it. A lost note is lost memory."""
    class MuteReflector(StubAgent):
        kind = "llm"
        reflect_system_text = "sys"

        def reflect(self, kind, system, user):
            return {"text": "   ", "raw": {"usage": {"completion_tokens": 3000}}}

    eng, sink, agents = engine_factory(periods=1, max_rounds_per_period=1)
    for s in ("S01", "S09"):
        agents[s] = MuteReflector(s)
    agents["S01"].turns = [q("bid", 300)]
    agents["S09"].accepts = True
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    eng.run_turn("S01", 1, 1)

    empties = [e for e in _events(sink, "violation") if e.payload["reason"] == "empty_note"]
    assert len(empties) == 2                      # both sides of the trade
    assert {e.seat for e in empties} == {"S01", "S09"}
    assert empties[0].payload["kind"] == "trade_feedback"
    assert eng.state["S01"].reflections == []     # nothing fabricated into memory


def test_reasoning_is_captured_and_never_fed_back(engine_factory):
    """The chain of thought is 91-96% of output tokens on this model and is the only
    direct record of HOW a price was reached — §11.3's primary evidence. It must reach the
    log, and it must never re-enter a prompt (DeepSeek's own guidance, and it would also
    hand an agent a transcript no subject ever had)."""
    from ps1982.agents.llm_agent import _envelope

    env = _envelope({"text": '{"ok":1}', "reasoning": "0.4*400 + 0.6*100 = 220"},
                    system="sys", user="usr")
    assert env["reasoning"] == "0.4*400 + 0.6*100 = 220"
    assert env["completion"] == '{"ok":1}'
    # A provider that returns nothing for it must not blow up the envelope.
    assert _envelope({"text": "x"}, system="s", user="u")["reasoning"] == ""

    # No briefing may ever quote it back.
    eng, sink, _ = engine_factory(periods=1, max_rounds_per_period=1)
    eng.state["S01"].reflections.append(
        {"kind": "period_end", "period": 1, "round": 0, "at": None, "text": "a note"})
    ctx = eng._turn_ctx("S01", 1, 1) if eng.cards else None
    eng.period, eng.info, eng.cards = 1, "none", {s: None for s in SEATS}
    mem = eng._memory("S01")
    assert "reasoning" not in mem
    assert all("reasoning" not in n for n in mem["reflections"])


def test_interrupt_and_resume_continues_the_same_session(engine_factory):
    """Stop on a period boundary, then carry on from the checkpoint.

    The things that must survive are the ones that would silently make the resumed run a
    DIFFERENT experiment: the seat->name mapping, each seat's accumulated notes and record,
    and above all the RNG state — reseeding would replay round orders and tie-breaks that
    the first half already consumed.
    """
    import threading

    eng, sink, _ = engine_factory(periods=6, max_rounds_per_period=1)
    stop = threading.Event()
    seen = []

    def after_period(e):
        seen.append(e.completed_periods)
        if e.completed_periods == 2:
            stop.set()

    eng.on_period_done = after_period
    assert eng.run_session(stop=stop) is None          # stopped, no summary
    assert seen == [1, 2]

    snap = eng.snapshot()
    assert snap["completed_periods"] == 2
    assert snap["next_event_id"] == sink.events[-1].event_id + 1
    rng_after_two = eng.rng.bit_generator.state["state"]

    # Resume into a fresh engine and finish the session.
    eng2, sink2, _ = engine_factory(periods=6, max_rounds_per_period=1)
    eng2._restore(snap)
    eng2.names = dict(snap["names"])
    assert eng2.completed_periods == 2
    assert eng2.names == eng.names
    assert eng2.rng.bit_generator.state["state"] == rng_after_two
    for s in SEATS:
        assert eng2.state[s].history == eng.state[s].history
        assert eng2.state[s].total_profit == eng.state[s].total_profit

    done = []
    eng2.on_period_done = lambda e: done.append(e.completed_periods)
    out = eng2.run_session()
    assert done == [3, 4, 5, 6]                        # picks up at 3, not 1
    assert out is not None and len(out["totals"]) == 12
    # No session_start on the resumed leg: the log already holds one.
    assert not [e for e in sink2.events if e.type == "session_start"]
    assert [e.payload["period"] for e in sink2.events if e.type == "period_end"] == [3, 4, 5, 6]


def test_resume_rejects_a_checkpoint_from_another_session(engine_factory):
    eng, _, _ = engine_factory(periods=2)
    snap = eng.snapshot()
    snap["session"] = 7
    eng2, _, _ = engine_factory(periods=2)
    with __import__("pytest").raises(ValueError, match="different session"):
        eng2._restore(snap)
    snap["session"], snap["version"] = 0, 99
    with __import__("pytest").raises(ValueError, match="version"):
        eng2._restore(snap)


def test_resume_drops_events_the_checkpoint_does_not_account_for(tmp_path):
    """A run killed MID-period leaves that period half-written. Resuming re-runs it, so the
    abandoned attempt has to go: metrics read the log, not the engine, and would otherwise
    count the dead period's trades twice."""
    from ps1982.cli import _truncate_to_checkpoint
    from ps1982.events import canonical_json

    log = tmp_path / "r.jsonl"
    rows = [{"event_id": i, "session": 0, "period": 1, "round": 0, "type": "book",
             "seat": None, "agent_visible": True, "payload": {}, "ts": ""} for i in range(10)]
    log.write_text("".join(canonical_json(r) + "\n" for r in rows) + "{tor", encoding="utf-8")

    dropped = _truncate_to_checkpoint(log, next_event_id=6)
    kept = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert dropped == 5                       # ids 6..9 plus the torn tail
    assert [r["event_id"] for r in kept] == [0, 1, 2, 3, 4, 5]

    # Idempotent: resuming twice must not eat committed events.
    assert _truncate_to_checkpoint(log, next_event_id=6) == 0


def test_each_channel_gets_its_own_output_budget(monkeypatch):
    """The three channels have separate token caps and each must actually be sent.

    `broadcast_max_output_tokens` was silently unused for the whole life of the project:
    the broadcast call passed `thinking` but not the cap, so every broadcast ran on the
    provider default of 8192 while the scenario said 512. Broadcasts are ~70% of all
    calls, so that is most of the token bill — and on a locally served Qwen3.6 the median
    broadcast came back at 1,830 tokens, which is what exposed it.
    """
    from ps1982.agents.llm_agent import LLMAgent
    from ps1982.config import AgentSpec, Rules
    from ps1982.markets import MARKETS

    seen = {}

    # Recorded against the REAL provider signatures, not a permissive **kw stub. A stub
    # that swallows anything hides exactly the bug this test exists for: complete_json did
    # not accept max_output_tokens at all, so passing it raised TypeError in production
    # while the test passed.
    import inspect

    from ps1982.llm.openai_compat import DeepSeekProvider

    for name in ("complete_json", "complete_text"):
        params = inspect.signature(getattr(DeepSeekProvider, name)).parameters
        assert "max_output_tokens" in params, f"{name} must take a per-call budget"

    class Rec:
        def complete_json(self, system, user, *, temperature=None, thinking=None,
                          max_output_tokens=None):
            seen[len(seen)] = max_output_tokens
            return {"data": {"response": "decline"}, "usage": None}

        def complete_text(self, system, user, *, temperature=None, thinking=None,
                          max_output_tokens=None):
            seen[len(seen)] = max_output_tokens
            return {"text": "note", "usage": None}

    spec = AgentSpec(kind="llm", max_output_tokens=8192,
                     broadcast_max_output_tokens=512, reflect_max_output_tokens=3000)
    monkeypatch.setattr("ps1982.agents.llm_agent.get_provider", lambda **kw: Rec())
    a = LLMAgent("S01", spec, Rules(), MARKETS[3], name="Nora")

    ctx = type("C", (), dict(
        seat="S01", period=1, info="none", card=None,
        quote={"side": "bid", "price": 200, "seat": "S07"},
        certs=2, cash=10_000, book={"bid": None, "ask": None, "spread": None},
        market_log=[], reflections=[], history=[], not_selected=[], names={"S01": "Nora"}))()
    a.respond_broadcast(ctx)
    assert seen[0] == 512, f"broadcast must send its own cap, got {seen[0]}"
