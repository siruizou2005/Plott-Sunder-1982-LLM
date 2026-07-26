"""Event model + canonical JSONL serialization.

One append-only stream is the single source of truth: the CLI, the post-hoc metrics and
the web visualiser all read the same file, and nothing has a second data path.

Two visibility tiers (design doc §10) are expressed by the ``agent_visible`` flag rather
than by two files. The agent-visible market log is DERIVED by filtering. This matters most
for ``broadcast``: the losing acceptors must be recorded (they are the potential demand
curve, data a human experiment cannot obtain) while staying invisible to agents.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
from dataclasses import dataclass

EVENT_TYPES = {
    # session / period structure
    "session_start",     # config snapshot, seed, sequence preset, model params
    "period_start",      # state theta, info condition, clue cards, insider roster (hidden)
    "round_start",       # the freshly randomized seat order for this round
    "period_end",        # theta revealed, per-seat dividend / cash / profit
    "session_end",       # per-seat totals in francs + USD, token and cost totals

    # the per-turn agent trail — the "as detailed as GMS" requirement
    "brief",             # the literal briefing text pushed to the agent
    "model_turn",        # full prompt + full completion + usage + retries + latency
    "agent_view",        # posterior / reservation_buy / reservation_sell / basis
    "action",            # no_quote | quote | accept_standing
    "violation",         # a rejected attempt: budget / no_inventory / no_improvement /
                         # stale_quote / malformed / illegal_accept
    "broadcast",         # recipients, each response, accept count, winner, LOSERS (hidden)
    "book",              # standing_bid / standing_ask / spread after every change
    "trade",             # buyer, seller, price, trigger
    "reflection",        # trade_feedback (1-2 sentences) | period_end (~100 words)
}

# Which event types enter the agent-visible market log (design doc §10.1). Everything else
# exists only in the computer log.
AGENT_VISIBLE_TYPES = {"action", "trade", "book"}


@dataclass
class Event:
    event_id: int
    period: int
    round: int
    type: str
    seat: str | None
    payload: dict
    agent_visible: bool = False
    ts: str = ""
    session: int = 0

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "session": self.session,
            "period": self.period,
            "round": self.round,
            "type": self.type,
            "seat": self.seat,
            "agent_visible": self.agent_visible,
            "payload": self.payload,
            "ts": self.ts,
        }


def canonical_json(d: dict) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def read_events(path: str) -> list[dict]:
    """Load a JSONL event log.

    Tolerates a single truncated FINAL line (a run killed mid-write leaves invalid JSON at
    the tail) so the valid prefix stays loadable; a corrupt INTERIOR line is genuine
    corruption and is re-raised, because silently dropping it would shift every later event.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = [line.strip() for line in fh if line.strip()]
    out: list[dict] = []
    for i, line in enumerate(raw):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            if i == len(raw) - 1:
                break
            raise
    return out


class EventSink:
    def emit(self, event: Event) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        pass


class ListSink(EventSink):
    """In-memory sink for tests."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)

    def of_type(self, *types: str) -> list[Event]:
        return [e for e in self.events if e.type in types]


class JsonlEventSink(EventSink):
    """Append-only JSONL, flushed per event so a crashed run still yields a readable log."""

    def __init__(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self._fh = open(path, "a", encoding="utf-8")

    def emit(self, event: Event) -> None:
        self._fh.write(canonical_json(event.to_dict()) + "\n")
        self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:  # noqa: BLE001
            pass


class FanoutSink(EventSink):
    def __init__(self, sinks: list[EventSink]) -> None:
        self.sinks = sinks

    def emit(self, event: Event) -> None:
        for s in self.sinks:
            s.emit(event)

    def close(self) -> None:
        for s in self.sinks:
            s.close()


class EventStream:
    """Assigns ids and timestamps, then fans out. Thread-safe: broadcast responses are
    collected concurrently and each emits its own event."""

    def __init__(self, sink: EventSink, *, start_id: int = 0) -> None:
        self.sink = sink
        # A resumed run appends to the same JSONL, so ids must carry on from where the
        # interrupted run stopped rather than restarting at 0 and colliding.
        self._next_id = start_id
        self._lock = threading.Lock()
        self.session = 0
        self.period = 0
        self.round = 0

    def emit(self, type: str, payload: dict, *, seat: str | None = None,
             agent_visible: bool | None = None, period: int | None = None,
             round: int | None = None) -> Event:
        assert type in EVENT_TYPES, f"unknown event type {type!r}"
        if agent_visible is None:
            agent_visible = type in AGENT_VISIBLE_TYPES
        with self._lock:
            ev = Event(
                event_id=self._next_id,
                session=self.session,
                period=self.period if period is None else period,
                round=self.round if round is None else round,
                type=type,
                seat=seat,
                payload=payload,
                agent_visible=agent_visible,
                ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
            )
            self._next_id += 1
            self.sink.emit(ev)
        return ev

    def next_id(self) -> int:
        """The id the next event will get — recorded so a resume continues the run."""
        with self._lock:
            return self._next_id

    def close(self) -> None:
        self.sink.close()
