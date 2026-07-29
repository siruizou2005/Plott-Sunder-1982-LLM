"""Scenario configuration (pydantic v2).

Follows the GMS convention: every treatment variable is a field with a default that
reproduces the baseline experiment, so adding a knob never perturbs an existing scenario.
Flipping one flag in YAML is enough to run a control arm — no code changes.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from dataclasses import replace

from .markets import MARKETS, Market
from .params import SEQUENCES, Sequence, random_sequence

# Not a frozen preset: the states are redrawn from the bingo cage per seed.
RANDOM_PRESET = "random_prior"


class Rules(BaseModel):
    """Institution-level treatment variables."""

    # Baseline (design doc §0.4): a new quote must strictly improve the standing quote on
    # its own side. False reproduces the paper's footnote 3 literally — "Only one (the
    # last) bid and offer are outstanding" — restoring the strategy of posting a WORSE
    # quote to bury someone else's signal (design doc §14.3).
    price_improvement: bool = True

    # Whether a no-information period is announced as such. FALSE is the faithful baseline:
    # Table 1 records market 3's common knowledge about informed agents as "How Many: No",
    # so subjects holding a blank card could not tell whether anyone else was informed.
    # True is the §14.4 treatment arm, which tests the paper's own conjecture about market
    # 4 — that "nobody knows that nobody is informed" inflates the subjective state space
    # and delays convergence.
    # None = follow the market, which is what the paper did: no-information periods were
    # announced in markets 1, 2 and 5 and not in 3 or 4. Set it explicitly only to run a
    # market against its own design as a treatment.
    announce_no_info_period: bool | None = None

    # Elicit posterior / reservation prices / basis each turn. Off = the reactivity control
    # (design doc §6 ②): belief elicitation may itself change behaviour.
    elicit_beliefs: bool = True

    # Ask each broadcast respondent for a <=15-word reason. Cheap and highly informative
    # for "which quotes leaked information", but it is another elicitation channel.
    broadcast_reason: bool = True

    # How many recent market-log entries an agent sees. 0 = the whole period (markets 5's
    # photocopy handout); 4 reproduces the blackboard, which held "the latest four or five".
    market_log_window: int = 0

    # How many of its own past notes an agent carries into a prompt (design doc §6 ①).
    #
    # The two kinds get SEPARATE budgets. Under one shared window they compete, and a busy
    # year settles enough trades to evict the year-end reflection — which design doc §8
    # calls the most important learning node — within a single period. Measured rate:
    # 0.9 post-trade notes per seat per period at one round (nothing evicted), but 3.4 on
    # average and up to 14 at the three rounds the real experiment runs.
    period_end_notes: int = 2
    trade_notes: int = 3

    # Acceptances that did not go through, shown from THIS period only and reset each year
    # like the market log. A subject who called out an acceptance and watched the
    # experimenter pick someone else knows perfectly well that it happened; a stateless
    # agent does not, unless it is told.
    not_selected_window: int = 5


class AgentSpec(BaseModel):
    """Agent roster entry. ``seats`` empty means 'every seat not claimed by another spec'."""

    kind: str = "llm"                       # llm | zi | pi | re
    seats: list[str] = Field(default_factory=list)
    model: str | None = None                # None -> $DEEPSEEK_MODEL
    # Where to send the request. Bailian serves the same deepseek-v4-flash weights behind an
    # OpenAI-compatible endpoint, so pointing these two at it is the whole vendor switch —
    # same provider class, same prompts, same engine. Both None keeps DeepSeek's own API.
    # A base_url of "$NAME" is read from the environment, so hosts stay out of the scenario
    # files alongside the keys. A gemini-* model ignores both and goes to Vertex via ADC.
    base_url: str | None = None
    api_key_env: str | None = None
    temperature: float = 0.7
    max_output_tokens: int = 2048
    thinking: bool = True
    reasoning_effort: str | None = None
    # Broadcast responses are ~70% of all calls, so design doc §13.2 proposes them as the
    # one place worth downgrading. Measurement says do NOT: with thinking off, 67% of the
    # broadcast replies that stated an expected value stated the WRONG one — type I agents
    # said 250 and type II said 225, i.e. (400+100)/2 and (300+150)/2, falling back on a
    # 50/50 prior instead of the bingo cage's 16/40. The same agents deciding on their own
    # turn with thinking on put 22 of 24 reservation prices exactly on their true prior EV.
    # Since most trades are struck through the broadcast channel, downgrading it would make
    # the run measure the model's arithmetic rather than whether the market aggregates
    # information. Kept as a flag so the cheap arm stays available and comparable.
    broadcast_thinking: bool = True
    broadcast_max_output_tokens: int = 512

    # Reflections used to run with thinking off. Measurement says they must not: of the
    # smoke run's notes that stated a prior expected value, 20 of 20 stated the WRONG one
    # (type I said 250, II said 225 — a 50/50 prior instead of the bingo cage's 16/40),
    # and not one was right. That is worse than the broadcast channel's 67%, and it does
    # more damage: a note becomes DURABLE memory, so the next turn — reasoning with
    # thinking on — reads "my expected value is 250" as its own past conclusion.
    reflect_thinking: bool = True
    # Reasoning tokens draw on the SAME budget as the note, so this has to clear the
    # reasoning plus the text. Measured on the probe run: notes that came back at all
    # spent 273-926 tokens thinking, but 6 of 12 year-end calls spent the entire 1200
    # reasoning and returned nothing. 400 (the original) and 1200 were both too tight.
    reflect_max_output_tokens: int = 3000
    repair_retries: int = 2
    pace: float = 0.25
    max_retries: int = 5


class Pricing(BaseModel):
    """USD per million tokens. Used only to report cost; set from the current price sheet."""

    input_per_mtok: float = 0.28
    cached_input_per_mtok: float = 0.028
    output_per_mtok: float = 0.42


class Config(BaseModel):
    run_name: str = "market3"
    seed: int = 20250725
    # Which of the paper's five markets. They are five TREATMENTS, not five samples: the
    # roster is nine agents in market 1 and twelve elsewhere, the prior is 1/3, .4 or a
    # three-way split, market 5 has a third state and the period count runs 11 to 14.
    market: int = 3
    sequence_preset: str = "paper_exact"
    sessions: int = 1
    max_rounds_per_period: int = 3          # design doc §7: 2-3 rounds per period
    periods: int | None = None              # None = the market's own count; smaller for smoke
    broadcast_workers: int = 12             # the only concurrency point in the engine
    rules: Rules = Field(default_factory=Rules)
    agents: list[AgentSpec] = Field(default_factory=lambda: [AgentSpec()])
    pricing: Pricing = Field(default_factory=Pricing)

    @model_validator(mode="after")
    def _check(self) -> "Config":
        if self.market not in MARKETS:
            raise ValueError(f"unknown market {self.market!r}; expected one of "
                             f"{sorted(MARKETS)}")
        if self.sequence_preset not in SEQUENCES and self.sequence_preset != RANDOM_PRESET:
            raise ValueError(f"unknown sequence_preset {self.sequence_preset!r}; "
                             f"expected one of {sorted(SEQUENCES) + [RANDOM_PRESET]}")
        # The hand-built market-3 presets cannot describe another market's roster, period
        # count or state set. Rejecting the combination is better than silently running
        # market 5 on twelve X/Y periods.
        if self.market != 3 and self.sequence_preset not in ("paper_exact", RANDOM_PRESET):
            raise ValueError(f"sequence_preset {self.sequence_preset!r} is market-3 only; "
                             f"market {self.market} takes 'paper_exact' or {RANDOM_PRESET!r}")
        for a in self.agents:
            if a.kind not in ("llm", "zi", "pi", "re", "inv"):
                raise ValueError(f"unknown agent kind {a.kind!r}")
        return self

    @property
    def market_spec(self) -> Market:
        """The Market this run is: its roster, prior, states, dividends and sequence.

        `random_prior` redraws each period's realized state from THIS market's own prior
        while holding its information design fixed — the design is the treatment, the
        realized states are one draw of it. Drawn from the seed, so it is reproducible and
        differs between sessions that differ only by seed, which is the point of running a
        second market on it.
        """
        m = MARKETS[self.market]
        if self.sequence_preset == RANDOM_PRESET:
            return m.redrawn(self.seed)
        if self.sequence_preset != "paper_exact":
            # A hand-built market-3 preset (the two-period probe). Validation above has
            # already established that self.market == 3.
            preset = SEQUENCES[self.sequence_preset]
            return replace(m, sequence_states=preset.states, sequence_info=preset.info,
                           note=preset.note)
        return m

    @property
    def sequence(self):
        """The realized states and information conditions, in the pre-Market shape.

        Kept because the cli, the metrics and the viewer read `.states` / `.info` /
        `.name`. It is now a view over `market_spec` rather than a separate source.
        """
        m = self.market_spec
        return Sequence(name=f"{self.sequence_preset}_m{self.market}",
                        states=m.sequence_states, info=m.sequence_info, note=m.note)

    @property
    def n_periods(self) -> int:
        full = self.market_spec.n_periods
        return min(self.periods or full, full)

    @property
    def uses_llm(self) -> bool:
        return any(a.kind == "llm" for a in self.agents)

    def spec_for(self, seat: str) -> AgentSpec:
        """Resolve a seat to its roster entry: an explicit ``seats`` list wins, otherwise
        the first spec with no seat list acts as the catch-all."""
        for a in self.agents:
            if seat in a.seats:
                return a
        for a in self.agents:
            if not a.seats:
                return a
        raise ValueError(f"no agent spec covers seat {seat}")


def load_config(path: str | Path) -> Config:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Config(**data)
