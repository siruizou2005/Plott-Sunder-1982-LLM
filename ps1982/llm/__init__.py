"""LLM provider package.

One interface, three ways to reach a model:

  * DeepSeek's own API                     — model deepseek-*, default endpoint
  * Bailian (Alibaba Model Studio)         — the same DeepSeek weights, OpenAI-compatible;
                                             set base_url + api_key_env in the scenario
  * Gemini on Vertex AI                    — model gemini-*, ADC auth

Which one is used is decided by the scenario, never by the engine, the agents or the
prompts — they are not aware there is more than one.
"""

from __future__ import annotations

import os

from .base import LLMProvider, Usage, _is_transient, _load_env  # noqa: F401
from .gemini import GeminiProvider  # noqa: F401
from .openai_compat import DeepSeekProvider, _extract_json  # noqa: F401


def _is_gemini(model: str | None) -> bool:
    return bool(model) and "gemini" in model.lower()


def get_provider(model: str | None = None, *, temperature: float = 0.7,
                 max_output_tokens: int = 2048, max_retries: int = 5, pace: float = 0.25,
                 thinking: bool = False, reasoning_effort: str | None = None,
                 repair_retries: int = 2, base_url: str | None = None,
                 api_key_env: str | None = None) -> LLMProvider:
    """Build the provider for ``model``; defaults to $DEEPSEEK_MODEL.

    A ``base_url`` beginning with ``$`` is read from the environment, which keeps hosts out
    of the scenario files alongside the keys.

    ``reasoning_effort`` is DeepSeek's knob; Gemini's equivalent is the thinking LEVEL and
    the two take different values, so it reaches Gemini under its own name rather than
    pretending one vocabulary covers both.
    """
    _load_env()
    name = model or os.environ.get("DEEPSEEK_MODEL")
    if base_url and base_url.startswith("$"):
        base_url = os.environ.get(base_url[1:])
    if _is_gemini(name):
        return GeminiProvider(model=name, temperature=temperature,
                              max_output_tokens=max_output_tokens, max_retries=max_retries,
                              pace=pace, thinking=thinking,
                              thinking_level=reasoning_effort,
                              repair_retries=repair_retries)
    return DeepSeekProvider(model=name, temperature=temperature,
                            max_output_tokens=max_output_tokens, max_retries=max_retries,
                            pace=pace, thinking=thinking, reasoning_effort=reasoning_effort,
                            repair_retries=repair_retries, base_url=base_url,
                            api_key_env=api_key_env or "DEEPSEEK_API_KEY")
