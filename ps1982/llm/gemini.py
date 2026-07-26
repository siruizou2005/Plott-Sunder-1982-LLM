"""Gemini on Vertex AI.

Same two-method contract as the DeepSeek provider — one structured-JSON completion or one
free-text completion per call, no tools, no conversation state — so the engine, the agents
and the prompts are untouched. Auth is ADC (`gcloud auth application-default login`);
project, location and model come from the .env, exactly as the DeepSeek settings do.

Three things differ from the OpenAI-compatible path and are handled here rather than
leaking upward:

* **Token accounting.** Gemini reports thinking tokens in `thoughts_token_count`, SEPARATE
  from `candidates_token_count`, whereas DeepSeek folds reasoning into
  `completion_tokens`. Both are billed as output. `completion_tokens` is therefore set to
  candidates + thoughts so `Usage.cost_usd` stays correct without a per-provider branch,
  and `reasoning_tokens` keeps the thinking part on its own for analysis.

* **JSON.** `response_mime_type="application/json"` is the equivalent of the OpenAI
  json_object mode. The brace-extraction fallback and the repair retries are kept
  identical, because a model that returns prose around its JSON is a failure mode of the
  prompt, not of the vendor.

* **Thinking.** Measured on gemini-3.5-flash: `thinking_level="minimal"` and
  `thinking_budget=0` both return no `thoughts_token_count` at all and answer in ~0.9s,
  against 404 thinking tokens and 3.5s when unset. So thinking genuinely can be turned off
  on this model — unlike Gemini 3.0, where it cannot. `minimal` is used because it is the
  documented lever for Gemini 3.x; the budget form is the 2.5-era one.
"""

from __future__ import annotations

import os
import time

from .base import LLMProvider, Usage, _is_transient, _jittered, _load_env
from .openai_compat import _extract_json


def _usage_from(resp) -> Usage:
    u = getattr(resp, "usage_metadata", None)
    if u is None:
        return Usage()
    g = lambda name: getattr(u, name, 0) or 0          # noqa: E731
    thoughts = g("thoughts_token_count")
    cached = g("cached_content_token_count")
    prompt = g("prompt_token_count")
    return Usage(
        prompt_tokens=prompt,
        # Thinking is billed as output; fold it in so the shared cost function is right.
        completion_tokens=g("candidates_token_count") + thoughts,
        cache_hit_tokens=cached,
        cache_miss_tokens=max(0, prompt - cached),
        reasoning_tokens=thoughts,
    )


def _text_and_thoughts(resp) -> tuple[str, str]:
    """Split the answer from the thinking parts.

    Gemini marks thinking parts with `part.thought`; the visible answer is everything else.
    `resp.text` raises rather than returning None on some shapes, so the parts are walked
    directly.
    """
    cand = (getattr(resp, "candidates", None) or [None])[0]
    content = getattr(cand, "content", None) if cand else None
    parts = (getattr(content, "parts", None) or []) if content else []
    answer, thinking = [], []
    for p in parts:
        t = getattr(p, "text", None)
        if not t:
            continue
        (thinking if getattr(p, "thought", False) else answer).append(t)
    return "".join(answer), "".join(thinking)


class GeminiProvider(LLMProvider):
    def __init__(self, model: str | None = None, temperature: float = 0.7,
                 max_output_tokens: int = 2048, max_retries: int = 5,
                 backoff_base: float = 2.0, pace: float = 0.25,
                 thinking: bool = False, thinking_level: str | None = None,
                 repair_retries: int = 2) -> None:
        _load_env()
        self.project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.pace = pace
        self.thinking = bool(thinking)
        # Level used when thinking is ON. None -> the model's own default.
        self.thinking_level = thinking_level
        self.repair_retries = repair_retries
        self._client = None

    def client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(vertexai=True, project=self.project,
                                        location=self.location)
        return self._client

    def _thinking_config(self, thinking: bool):
        from google.genai import types
        if not thinking:
            # Verified on gemini-3.5-flash: no thoughts_token_count is reported at all.
            return types.ThinkingConfig(thinking_level="minimal")
        if self.thinking_level:
            return types.ThinkingConfig(thinking_level=self.thinking_level)
        return None

    def _call(self, system: str, user: str, *, temperature: float, thinking: bool,
              json_mode: bool, max_output_tokens: int) -> dict:
        """One request with the shared retry/backoff/pace loop. Never raises."""
        from google.genai import types
        cfg = dict(system_instruction=system, temperature=temperature,
                   max_output_tokens=max_output_tokens,
                   thinking_config=self._thinking_config(thinking))
        if json_mode:
            cfg["response_mime_type"] = "application/json"

        transient_tries = 0
        backoff_s = 0.0
        t0 = time.monotonic()
        while True:
            if self.pace:
                time.sleep(self.pace)
            try:
                resp = self.client().models.generate_content(
                    model=self.model, contents=user,
                    config=types.GenerateContentConfig(**cfg))
            except Exception as e:  # noqa: BLE001
                error = str(e)
                if _is_transient(error) and transient_tries < self.max_retries:
                    transient_tries += 1
                    sleep_s = _jittered(self.backoff_base, transient_tries)
                    backoff_s += sleep_s
                    print(f"[rate-limit] {self.model}: transient error, retry "
                          f"{transient_tries}/{self.max_retries} after {sleep_s:.0f}s "
                          f"backoff ({error[:60]})", flush=True)
                    time.sleep(sleep_s)
                    continue
                return {"text": "", "reasoning": "", "error": error,
                        "api_error": _is_transient(error), "retries": transient_tries,
                        "backoff_s": backoff_s, "usage": Usage(),
                        "latency_s": time.monotonic() - t0}

            text, thoughts = _text_and_thoughts(resp)
            return {"text": text, "reasoning": thoughts, "error": None, "api_error": False,
                    "retries": transient_tries, "backoff_s": backoff_s,
                    "usage": _usage_from(resp), "latency_s": time.monotonic() - t0}

    # ---------------------------------------------------------------- interface

    def complete_json(self, system: str, user: str, *, temperature: float | None = None,
                      thinking: bool | None = None,
                      max_output_tokens: int | None = None) -> dict:
        # Same signature as the OpenAI-compatible provider: the caller decides the budget
        # per channel, and the broadcast channel is 70% of all calls.
        temp = self.temperature if temperature is None else temperature
        think = self.thinking if thinking is None else thinking
        cap = self.max_output_tokens if max_output_tokens is None else max_output_tokens
        usage = Usage()
        repairs = retries = 0
        backoff_s = latency = 0.0
        prompt = user
        last_text = last_reasoning = ""
        last_error: str | None = None
        api_error = False

        while True:
            r = self._call(system, prompt, temperature=temp, thinking=think,
                           json_mode=True, max_output_tokens=cap)
            usage += r["usage"]
            retries += r["retries"]
            backoff_s += r["backoff_s"]
            latency += r["latency_s"]
            last_text = r["text"]
            last_reasoning = r.get("reasoning", "")
            if r["error"]:
                last_error, api_error = r["error"], r["api_error"]
                break
            data = _extract_json(last_text)
            if data is not None:
                return {"data": data, "text": last_text, "reasoning": last_reasoning,
                        "error": None, "api_error": False, "retries": retries,
                        "backoff_s": backoff_s, "repairs": repairs, "usage": usage,
                        "latency_s": latency}
            last_error = "unparseable JSON"
            if repairs >= self.repair_retries:
                break
            repairs += 1
            prompt = (f"{user}\n\n---\nYour previous reply could not be parsed as JSON. "
                      f"Reply with the JSON object only — no prose, no code fences.\n"
                      f"Previous reply was:\n{last_text[:500]}")

        return {"data": None, "text": last_text, "reasoning": last_reasoning,
                "error": last_error, "api_error": api_error, "retries": retries,
                "backoff_s": backoff_s, "repairs": repairs, "usage": usage,
                "latency_s": latency}

    def complete_text(self, system: str, user: str, *, temperature: float | None = None,
                      thinking: bool | None = None,
                      max_output_tokens: int | None = None) -> dict:
        temp = self.temperature if temperature is None else temperature
        think = self.thinking if thinking is None else thinking
        r = self._call(system, user, temperature=temp, thinking=think, json_mode=False,
                       max_output_tokens=max_output_tokens or self.max_output_tokens)
        r["repairs"] = 0
        return r
