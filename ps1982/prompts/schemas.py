"""JSON schemas for the three structured agent replies, plus tolerant coercion.

DeepSeek's json_object mode constrains the decoder to emit valid JSON, not to match a
schema — so we validate here and repair what is safely repairable (a probability given as
"0.72", a price given as 310.0, "BID" instead of "bid"). Anything that survives coercion
and still fails validation is a genuine malformed reply: the caller records a violation
and falls back to the safe default.
"""

from __future__ import annotations

from functools import lru_cache

from jsonschema import Draft202012Validator

BASIS_VALUES = ["prior", "clue", "price", "others_behavior", "spread"]

_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"enum": ["no_quote", "quote", "accept_standing"]},
        "side": {"enum": ["bid", "ask"]},
        "price": {"type": "integer", "minimum": 1},
    },
    "required": ["type"],
    "allOf": [
        {"if": {"properties": {"type": {"const": "quote"}}, "required": ["type"]},
         "then": {"required": ["side", "price"]}},
        {"if": {"properties": {"type": {"const": "accept_standing"}}, "required": ["type"]},
         "then": {"required": ["side"]}},
    ],
}

def posterior_schema(states=("X", "Y")) -> dict:
    """The belief object for a market with `states`.

    Market 5 has three states. A two-state schema would reject every well-formed reply it
    ever produced, and the engine turns a schema failure into a forced no_quote — an agent
    that decided to trade recorded as having passed, in every period of the market.
    """
    return {
        "type": "object",
        "properties": {s: {"type": "number", "minimum": 0, "maximum": 1} for s in states},
        "required": list(states),
    }


TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "posterior": posterior_schema(),
        "reservation_buy": {"type": "integer", "minimum": 0},
        "reservation_sell": {"type": "integer", "minimum": 0},
        "basis": {"enum": BASIS_VALUES},
        "action": _ACTION_SCHEMA,
    },
    "required": ["posterior", "reservation_buy", "reservation_sell", "basis", "action"],
}

TURN_SCHEMA_NO_BELIEFS = {
    "type": "object",
    "properties": {"action": _ACTION_SCHEMA},
    "required": ["action"],
}

BROADCAST_SCHEMA = {
    "type": "object",
    "properties": {"response": {"enum": ["accept", "decline"]},
                   "why": {"type": "string"}},
    "required": ["response"],
}

_VALIDATORS = {
    "turn": Draft202012Validator(TURN_SCHEMA),
    "turn_no_beliefs": Draft202012Validator(TURN_SCHEMA_NO_BELIEFS),
    "broadcast": Draft202012Validator(BROADCAST_SCHEMA),
}


def _as_int(v):
    """Accept 310, 310.0, "310", " 310 " — reject 310.5 and anything non-numeric."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if float(v).is_integer() else None
    if isinstance(v, str):
        try:
            f = float(v.strip())
        except ValueError:
            return None
        return int(f) if f.is_integer() else None
    return None


def _as_float(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip().rstrip("%"))
        except ValueError:
            return None
    return None


def coerce_turn(data: dict, *, elicit_beliefs: bool,
                states: tuple[str, ...] = ("X", "Y")) -> dict:
    """Normalize a turn reply in place-ish, returning a new dict."""
    out = dict(data or {})

    act = out.get("action")
    if isinstance(act, str):                      # model wrote "no_quote" instead of an object
        act = {"type": act}
    if isinstance(act, dict):
        act = dict(act)
        t = act.get("type") or act.get("action")
        if isinstance(t, str):
            act["type"] = t.strip().lower()
        act.pop("action", None)
        s = act.get("side")
        if isinstance(s, str):
            s = s.strip().lower()
            act["side"] = {"buy": "bid", "sell": "ask"}.get(s, s)
        if "price" in act:
            p = _as_int(act["price"])
            if p is None:
                act.pop("price")
            else:
                act["price"] = p
        # A "quote"/"accept_standing" with no side is unrecoverable; leave it to validation.
        out["action"] = act

    if not elicit_beliefs:
        return {"action": out.get("action")}

    post = out.get("posterior")
    if isinstance(post, dict):
        vals = {s: _as_float(post.get(s)) for s in states}
        missing = [s for s, v in vals.items() if v is None]
        # Exactly one missing value is recoverable — it is whatever is left over. Two or
        # more are not, and guessing would invent a belief the model never stated.
        if len(missing) == 1:
            vals[missing[0]] = 1.0 - sum(v for v in vals.values() if v is not None)
            missing = []
        if not missing:
            total = sum(vals.values())
            # Models sometimes emit percentages (72 / 28) or values that miss 1.0 slightly.
            if total > 0:
                out["posterior"] = {s: round(v / total, 6) for s, v in vals.items()}

    for k in ("reservation_buy", "reservation_sell"):
        if k in out:
            v = _as_int(out[k])
            if v is None:
                out.pop(k)
            else:
                out[k] = max(0, v)

    b = out.get("basis")
    if isinstance(b, str):
        out["basis"] = b.strip().lower().replace(" ", "_").replace("-", "_")

    return out


def coerce_broadcast(data: dict) -> dict:
    out = dict(data or {})
    r = out.get("response")
    if isinstance(r, bool):
        r = "accept" if r else "decline"
    if isinstance(r, str):
        r = r.strip().lower()
        r = {"yes": "accept", "no": "decline", "y": "accept", "n": "decline",
             "true": "accept", "false": "decline"}.get(r, r)
    out["response"] = r
    if "why" in out and not isinstance(out["why"], str):
        out.pop("why")
    return out


@lru_cache(maxsize=8)
def _turn_validator(states: tuple[str, ...]):
    """A turn validator for a non-X/Y state set. Cached: this is on the reply path."""
    schema = {**TURN_SCHEMA, "properties": {**TURN_SCHEMA["properties"],
                                            "posterior": posterior_schema(states)}}
    return Draft202012Validator(schema)


def validate(kind: str, data: dict, states: tuple[str, ...] = ("X", "Y")) -> list[str]:
    """Return a list of human-readable errors; empty means valid.

    `states` rebuilds the turn validator for a market whose state set is not X/Y. Cached
    per state set rather than rebuilt per call, since this runs on every model reply.
    """
    if kind == "turn" and tuple(states) != ("X", "Y"):
        return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
                for e in sorted(_turn_validator(tuple(states)).iter_errors(data or {}),
                                key=lambda e: list(e.path))]
    v = _VALIDATORS[kind]
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in sorted(v.iter_errors(data or {}), key=lambda e: list(e.path))]
