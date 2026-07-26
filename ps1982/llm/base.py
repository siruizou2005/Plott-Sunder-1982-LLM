"""Provider-neutral LLM interface and shared helpers.

Ported from 02-GMS-Project/market_sim/llm/base.py. The transient-error detection is kept
VERBATIM (it was tuned against real DeepSeek failures); what changes is the abstract
method: this experiment pushes a complete briefing and asks for one structured JSON
object per call, so there is no tool loop and no multi-turn conversation.
"""

from __future__ import annotations

import os
import random
import re
from abc import ABC, abstractmethod
from pathlib import Path

# project root — wherever this checkout lives (this file is ps1982/llm/base.py)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The DeepSeek account is shared with the GMS project; fall back to its .env so a fresh
# checkout without a local .env still runs.
_FALLBACK_ENV = Path("/Users/zousirui/Project/02-GMS-Project/.env")

# Textual markers of a transient/infra error (retry with backoff, not a model failure).
# Network/DNS/connection blips all clear on a backoff-and-retry; treating them as hard
# failures would make an agent needlessly skip its turn. (Status codes are handled
# separately below so a digit string can't false-match inside an unrelated number.)
_TRANSIENT = ("resource_exhausted", "rate limit", "unavailable",
              "internal", "deadline", "timeout", "temporarily", "overloaded",
              "nameresolution", "failed to resolve", "max retries exceeded", "getaddrinfo",
              "temporary failure in name", "connection", "connection aborted",
              "connection reset", "connection refused", "newconnectionerror", "eof occurred")

# Retryable HTTP status codes, matched ONLY as standalone tokens (not as a substring of a
# larger number). This stops a permanent 400 whose message embeds a count — e.g.
# "...resulted in 16500 tokens" — from being misread as a transient "500" and retried.
_TRANSIENT_CODES = ("408", "409", "429", "500", "502", "503", "504")
_CODE_RE = re.compile(r"(?<!\d)(?:" + "|".join(_TRANSIENT_CODES) + r")(?!\d)")


# Retry backoff jitter. Its own Random instance on purpose: the experiment's draws come
# from a seeded numpy generator, and retry timing must never be able to perturb them.
_JITTER = random.Random()


def _jittered(base: float, attempt: int) -> float:
    """Exponential backoff with full jitter, floored at half a second.

    Deterministic ``base ** attempt`` backoff is a thundering herd. Every request a rate
    limit rejects in the same instant then wakes in the same instant and retries
    together, so one burst of congestion becomes a synchronised series of them — and
    this batch runs 25 sessions x 3 workers against one endpoint, which is exactly the
    shape that produces simultaneous rejections.

    Sampling uniformly over the whole window (AWS's "full jitter") decorrelates them; it
    beats both no-jitter and half-window schemes in their published comparison. The floor
    only stops a near-zero draw from becoming an instant re-hammer.
    """
    return max(0.5, _JITTER.uniform(0.0, base ** attempt))


def _is_transient(msg: str) -> bool:
    m = (msg or "").lower()
    if any(s in m for s in _TRANSIENT):
        return True
    return bool(_CODE_RE.search(m))


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        local = _PROJECT_ROOT / ".env"
        load_dotenv(local if local.exists() else _FALLBACK_ENV)
    except Exception:  # noqa: BLE001 — python-dotenv absent; env may already be set
        pass


class Usage:
    """Token counts for one call, plus the cost implied by a price table.

    DeepSeek reports cache hits separately (``prompt_cache_hit_tokens`` /
    ``prompt_cache_miss_tokens``); cached input is billed at a lower rate. Every seat's
    system prompt is byte-stable for a whole session, so the hit rate should be high —
    tracking it is how we verify that.
    """

    __slots__ = ("prompt_tokens", "completion_tokens", "cache_hit_tokens",
                 "cache_miss_tokens", "reasoning_tokens")

    def __init__(self, prompt_tokens: int = 0, completion_tokens: int = 0,
                 cache_hit_tokens: int = 0, cache_miss_tokens: int = 0,
                 reasoning_tokens: int = 0) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.cache_hit_tokens = cache_hit_tokens
        self.cache_miss_tokens = cache_miss_tokens
        self.reasoning_tokens = reasoning_tokens

    @classmethod
    def from_response(cls, resp) -> "Usage":
        u = getattr(resp, "usage", None)
        if u is None:
            return cls()
        details = getattr(u, "completion_tokens_details", None)
        prompt = getattr(u, "prompt_tokens", 0) or 0

        # Cache hits: prefer the OpenAI-standard `prompt_tokens_details.cached_tokens`,
        # which every compatible host emits, and fall back to DeepSeek's own top-level pair.
        # Reading only the DeepSeek fields reported a flat 0% hit rate on Bailian — which
        # serves the same model and does cache (0 -> 1024 -> 1536 as it warms) but does not
        # emit `prompt_cache_hit_tokens`. Silent, and a fivefold error in the cost estimate.
        pdet = getattr(u, "prompt_tokens_details", None)
        hit = getattr(pdet, "cached_tokens", None) if pdet else None
        if hit is None:
            hit = getattr(u, "prompt_cache_hit_tokens", 0) or 0
        miss = getattr(u, "prompt_cache_miss_tokens", None)
        if miss is None:
            miss = max(0, prompt - hit)

        return cls(
            prompt_tokens=prompt,
            completion_tokens=getattr(u, "completion_tokens", 0) or 0,
            cache_hit_tokens=hit or 0,
            cache_miss_tokens=miss or 0,
            reasoning_tokens=getattr(details, "reasoning_tokens", 0) or 0 if details else 0,
        )

    def to_dict(self) -> dict:
        return {"prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "cache_hit_tokens": self.cache_hit_tokens,
                "cache_miss_tokens": self.cache_miss_tokens,
                "reasoning_tokens": self.reasoning_tokens}

    def __iadd__(self, other: "Usage") -> "Usage":
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.cache_hit_tokens += other.cache_hit_tokens
        self.cache_miss_tokens += other.cache_miss_tokens
        self.reasoning_tokens += other.reasoning_tokens
        return self

    def cost_usd(self, pricing) -> float:
        """USD cost under a Pricing block (per-million-token rates).

        Cached and uncached input are billed separately when the provider reports the
        split; otherwise the whole prompt is billed at the uncached rate.
        """
        hit, miss = self.cache_hit_tokens, self.cache_miss_tokens
        if hit + miss == 0:
            hit, miss = 0, self.prompt_tokens
        return ((miss * pricing.input_per_mtok
                 + hit * pricing.cached_input_per_mtok
                 + self.completion_tokens * pricing.output_per_mtok) / 1_000_000.0)


class LLMProvider(ABC):
    """One structured-JSON completion per call. No tools, no conversation state."""

    @abstractmethod
    def complete_json(self, system: str, user: str, *, temperature: float | None = None,
                      thinking: bool | None = None) -> dict:
        """Returns::

            {"data": <parsed dict | None>, "text": <raw completion>,
             "error": str | None, "api_error": bool,
             "retries": int, "backoff_s": float, "repairs": int,
             "usage": Usage, "latency_s": float}

        ``data`` is None when the model never produced parseable JSON; the caller decides
        the fallback (skip the turn / decline the broadcast) and logs a violation.
        """
        raise NotImplementedError

    @abstractmethod
    def complete_text(self, system: str, user: str, *, temperature: float | None = None,
                      thinking: bool | None = None, max_output_tokens: int | None = None) -> dict:
        """Free-text completion (used for reflections). Same envelope, ``data`` absent."""
        raise NotImplementedError
