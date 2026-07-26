"""DeepSeek (OpenAI-compatible) provider.

Ported from 02-GMS-Project/market_sim/llm/openai_compat.py. The retry/backoff/pace loop,
the transient classification and the empty-``choices`` guard are kept as-is; the
function-calling path is replaced by JSON-object output, since this experiment pushes a
complete briefing and wants exactly one structured object back.

Three JSON-robustness layers, in order:
  1. ``response_format={"type": "json_object"}`` — DeepSeek constrains the decoder.
  2. brace extraction — salvages a JSON body wrapped in prose or fences.
  3. repair retries — re-ask with the parse error appended, up to ``repair_retries``.
"""

from __future__ import annotations

import json
import os
import time

from .base import LLMProvider, Usage, _is_transient, _jittered, _load_env


def _openai_transient(e) -> bool:
    """True for rate-limit / timeout / connection / 5xx errors that clear on retry."""
    try:
        from openai import (RateLimitError, APITimeoutError, APIConnectionError,
                            InternalServerError)
        if isinstance(e, (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)):
            return True
    except Exception:  # noqa: BLE001 — openai not importable; fall back to the string heuristic
        pass
    code = getattr(e, "status_code", None)
    if code in (408, 409, 429, 500, 502, 503, 504):
        return True
    return _is_transient(str(e))


def _extract_json(text: str):
    """Best-effort: parse the outermost {...} block as JSON. Returns dict or None."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


class DeepSeekProvider(LLMProvider):
    def __init__(self, model: str | None = None, *, base_url: str | None = None,
                 api_key_env: str = "DEEPSEEK_API_KEY", default_model_env: str = "DEEPSEEK_MODEL",
                 temperature: float = 0.7, max_output_tokens: int = 2048,
                 max_retries: int = 5, backoff_base: float = 2.0, pace: float = 0.25,
                 thinking: bool = False, reasoning_effort: str | None = None,
                 repair_retries: int = 2) -> None:
        _load_env()
        self.model = model or os.environ.get(default_model_env) or "deepseek-v4-flash"
        self.base_url = base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.api_key = os.environ.get(api_key_env)
        self.api_key_env = api_key_env
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.pace = pace
        self.thinking = bool(thinking)
        self.reasoning_effort = reasoning_effort
        self.repair_retries = repair_retries
        # The hybrid V4 models (deepseek-v4-flash / -pro) DEFAULT TO THINKING ENABLED, so
        # turning thinking OFF needs an explicit {"type": "disabled"} — omitting the field
        # would still think. The legacy aliases fix the mode by name (deepseek-chat =
        # non-thinking always, deepseek-reasoner = thinking always) and ignore the toggle.
        # (api-docs.deepseek.com/guides/thinking_mode)
        _name = (self.model or "").lower()
        self._hybrid = "reasoner" not in _name and "chat" not in _name
        self._client = None

    # ---------------------------------------------------------------- plumbing

    def client(self):
        if self._client is None:
            from openai import OpenAI
            kw = {}
            if self.api_key:
                kw["api_key"] = self.api_key
            if self.base_url:
                kw["base_url"] = self.base_url
            self._client = OpenAI(**kw)
        return self._client

    def _thinking_body(self, thinking: bool) -> dict | None:
        if not self._hybrid:
            return None
        return {"thinking": {"type": "enabled" if thinking else "disabled"}}

    def _call(self, system: str, user: str, *, temperature: float, thinking: bool,
              json_mode: bool, max_output_tokens: int) -> dict:
        """One request with the shared retry/backoff/pace loop. Never raises."""
        kwargs = dict(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=max_output_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        # A reasoning model rejects a custom temperature; a non-thinking call keeps it.
        if not thinking:
            kwargs["temperature"] = temperature
        elif self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        body = self._thinking_body(thinking)
        if body:
            kwargs["extra_body"] = body

        transient_tries = 0
        backoff_s = 0.0
        t0 = time.monotonic()
        while True:
            if self.pace:
                time.sleep(self.pace)
            try:
                resp = self.client().chat.completions.create(**kwargs)
            except Exception as e:  # noqa: BLE001
                error = str(e)
                if _openai_transient(e) and transient_tries < self.max_retries:
                    transient_tries += 1
                    sleep_s = _jittered(self.backoff_base, transient_tries)
                    backoff_s += sleep_s
                    print(f"[rate-limit] {self.model}: transient error, retry "
                          f"{transient_tries}/{self.max_retries} after {sleep_s:.0f}s backoff "
                          f"({error[:60]})", flush=True)
                    time.sleep(sleep_s)
                    continue
                return {"text": "", "reasoning": "", "error": error,
                        "api_error": _openai_transient(e),
                        "retries": transient_tries, "backoff_s": backoff_s,
                        "usage": Usage(), "latency_s": time.monotonic() - t0}

            # A 200 with empty `choices` happens on content filtering / empty generation;
            # return the neutral failure dict rather than raising an IndexError upward.
            choices = getattr(resp, "choices", None) or []
            if not choices or getattr(choices[0], "message", None) is None:
                return {"text": "", "reasoning": "", "error": "empty choices in response",
                        "api_error": False,
                        "retries": transient_tries, "backoff_s": backoff_s,
                        "usage": Usage.from_response(resp), "latency_s": time.monotonic() - t0}
            msg = choices[0].message
            # The chain of thought. It is 91-96% of the output tokens on this model and
            # was being discarded after we paid for it — while being the only direct
            # record of HOW an agent reached its price, which is what the experiment is
            # about. Never fed back to a model: DeepSeek's own guidance is that
            # reasoning_content must not re-enter the context.
            return {"text": msg.content or "",
                    "reasoning": getattr(msg, "reasoning_content", None) or "",
                    "error": None, "api_error": False,
                    "retries": transient_tries, "backoff_s": backoff_s,
                    "usage": Usage.from_response(resp), "latency_s": time.monotonic() - t0}

    # ---------------------------------------------------------------- interface

    def complete_json(self, system: str, user: str, *, temperature: float | None = None,
                      thinking: bool | None = None) -> dict:
        temp = self.temperature if temperature is None else temperature
        think = self.thinking if thinking is None else thinking
        usage = Usage()
        repairs = 0
        retries = 0
        backoff_s = 0.0
        latency = 0.0
        prompt = user
        last_text = ""
        last_reasoning = ""
        last_error: str | None = None
        api_error = False

        while True:
            r = self._call(system, prompt, temperature=temp, thinking=think,
                           json_mode=True, max_output_tokens=self.max_output_tokens)
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
                        "error": None, "api_error": False,
                        "retries": retries, "backoff_s": backoff_s, "repairs": repairs,
                        "usage": usage, "latency_s": latency}
            last_error = "unparseable JSON"
            if repairs >= self.repair_retries:
                break
            repairs += 1
            prompt = (f"{user}\n\n---\nYour previous reply could not be parsed as JSON. "
                      f"Reply with the JSON object only — no prose, no code fences.\n"
                      f"Previous reply was:\n{last_text[:500]}")

        return {"data": None, "text": last_text, "reasoning": last_reasoning,
                "error": last_error, "api_error": api_error,
                "retries": retries, "backoff_s": backoff_s, "repairs": repairs,
                "usage": usage, "latency_s": latency}

    def complete_text(self, system: str, user: str, *, temperature: float | None = None,
                      thinking: bool | None = None, max_output_tokens: int | None = None) -> dict:
        temp = self.temperature if temperature is None else temperature
        think = self.thinking if thinking is None else thinking
        r = self._call(system, user, temperature=temp, thinking=think, json_mode=False,
                       max_output_tokens=max_output_tokens or self.max_output_tokens)
        r["repairs"] = 0
        return r
