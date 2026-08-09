"""Scenario configuration (pydantic v2).

Follows the GMS convention: every treatment variable is a field with a default that
reproduces the baseline experiment, so adding a knob never perturbs an existing scenario.
Flipping one flag in YAML is enough to run a control arm — no code changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

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

    # Structural disclosure. FALSE is the faithful baseline: Table 1 records the common
    # knowledge about informed agents as "How Many: No", and design doc §3.3 keeps the
    # number of types, others' dividends and the informed count out of every prompt. True
    # writes the STRUCTURE in: the full per-type dividend table with the agent's own type
    # named, four investors per type, and that in a year when clue cards that are not
    # blank are handed out, exactly two of each type's four hold one. Identities, whether
    # the two stay the same across years, and the schedule of card years all stay hidden,
    # and the wording keeps the bingo-cage vocabulary (no probability language, the prior
    # only ever as balls). Only defined for markets whose information design never deals
    # cards to everyone — an 'all' period would make the two-per-type sentence false, and
    # Config._check rejects the combination.
    disclose_structure: bool = False

    # --- the disclosure ladder, tiers 2 and 3 (docs/disclosure-treatment.md).
    #
    # Both sit ON TOP of disclose_structure and Config._check refuses them without it, so
    # the treatment is a LADDER rather than a lattice: tier 1 is disclose_structure alone,
    # tier 2 adds disclose_card_years, tier 3 adds disclose_insiders_fixed. Every field
    # here defaults to False, so the baseline and the three completed tier-1 sessions
    # render byte-identical prompts — which prefix caching and every paired comparison
    # depend on, and tests/test_prompts.py's digests enforce.
    #
    # What stays hidden at EVERY rung: which investors hold the cards. Identities are not
    # a rung of this ladder and there is no flag that discloses them.

    # Tier 2. Whether each year is announced as one in which clue cards that are not blank
    # were handed out — in BOTH directions, every year, in the same words for every seat,
    # so an agent holding a letter learns nothing here that a blank-card holder does not.
    # It also replaces the tier-1 section's closing sentence, which says such years are not
    # announced and would become false.
    #
    # This SUBSUMES announce_no_info_period, which speaks only in the "none" direction: the
    # two write the same sentence there and share one branch in brief.py, so no
    # configuration can print it twice. An explicit announce_no_info_period: false beside
    # this flag asks for silence and for an announcement at once, and Config._check refuses
    # it rather than letting an invisible winner decide.
    disclose_card_years: bool = False

    # Tier 3. Whether the card holders are stated to be the same investors in every year
    # cards are handed out. True of the engine rather than asserted: Market.insiders is the
    # first `insiders_per_type` seats of each type block, derived from the roster, and
    # neither the period nor `redrawn` moves it — engine.py already records it as
    # "fixed_insiders" in period_start, and a test pins the wording to the engine.
    disclose_insiders_fixed: bool = False

    # An explicit objective, rendered as its own block of the SHARED preamble so that it
    # reaches the turn, the broadcast and the reflection prompts alike. The baseline states
    # its purpose only in _TURN_TASK ("You are free to make as much profit as you can"),
    # which is the paper's own wording and therefore never reaches a broadcast reply or a
    # year-end note — the two channels that between them carry 73% of all calls and all of
    # the durable memory. That sentence stays; this adds to it rather than replacing it.
    #
    # Not gated on a market: it says nothing about the information design.
    objective_profit_max: bool = False

    # Emphatic certainty for a clue card that carries a letter. NOT a new fact — the
    # instructions already say such a card "is always correct" and the year's card line
    # already says the dividend WILL be paid. This strengthens the wording in both places
    # and states nothing the baseline did not. Undefined for market 1, whose card is a
    # ten-draw sample that either box can produce, so Config._check refuses it there and
    # the imperfect-clue branch could not render it anyway.
    clue_is_certain: bool = False

    # Elicit posterior / reservation prices / basis each turn. Off = the reactivity control
    # (design doc §6 ②): belief elicitation may itself change behaviour.
    elicit_beliefs: bool = True

    # Ask each broadcast respondent for a <=15-word reason. Cheap and highly informative
    # for "which quotes leaked information", but it is another elicitation channel.
    broadcast_reason: bool = True

    # How many recent market-log entries an agent sees. 0 = the whole period (markets 5's
    # photocopy handout); 4 reproduces the blackboard, which held "the latest four or five".
    market_log_window: int = 0

    # What an agent writes when a market year ends (docs/design-deltas.md §5.4).
    #
    # "note" is the baseline and the default: about 100 words about the year just closed,
    # written fresh each time, with the last `period_end_notes` of them carried forward.
    # Measured over two completed sessions the model honours that ask tightly — median 105
    # words — so fourteen years produce fourteen short, disconnected notes and a window of
    # two, which means a conclusion reached in year 3 is gone by year 6 unless the agent
    # happens to restate it.
    #
    # "memo" replaces that with ONE standing document the agent rewrites at every year
    # end. The previous version is in the prompt verbatim and the new one REPLACES it, so
    # what survives is what the agent chose to carry — which is the point, and is also
    # what makes the length honest. The window drops to 1 because the memo already
    # contains its own history; Config._check enforces that rather than trusting the
    # scenario, since two 800-word memos in every prompt is ~900 wasted tokens per call
    # across the ~96% of calls that carry notes.
    period_end_style: Literal["note", "memo"] = "note"

    # The memo's target length, rendered as "between {lo} and {hi} words". Read only under
    # the memo style. Lives in the brief rather than the system prompt, which is where the
    # note style's "about 100 words" already sits — the system prompt says what kind of
    # document it is, the brief says how long this one should be.
    memo_words: tuple[int, int] = (500, 800)

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
    # Caps the engine's TWO wide pools — the broadcast (engine.py:352) and the period-end
    # notes (engine.py:666). A third pool, the two trade notes after a settlement
    # (engine.py:289), is fixed at 2 and is not covered by this.
    #
    # It is nonetheless the whole story for load, because the pools are never open at the
    # same time: a session drives its phases on one thread and every pool is entered
    # through a blocking `list(pool.map(...))` inside a `with`, so the pool has closed
    # before the next phase begins. In-flight requests per session are therefore bounded by
    # max(broadcast_workers, 2), and `sessions x broadcast_workers` is a mathematical
    # ceiling rather than a statistical hope — which is what the scenario files' concurrency
    # arithmetic rests on. Measured mean is ~1.9 per session; the ceiling is reached only
    # when every session happens to be mid-broadcast.
    broadcast_workers: int = 12
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
        # The disclosure text states that lettered cards go to two investors per type.
        # A market with 'all' periods hands one to everybody in those periods, which
        # would make the stated structure false. Rejecting the combination is better
        # than prompting agents with a lie.
        if self.rules.disclose_structure and "all" in self.market_spec.sequence_info:
            raise ValueError(
                f"disclose_structure states that lettered clue cards go to two investors "
                f"per type; market {self.market} has 'all' periods where every investor "
                f"receives one, so the disclosure text would be false")
        # The ladder is a ladder. Both higher rungs write into or refer to the section
        # disclose_structure creates: without it, fixedness has no sentence to modify and
        # the per-year announcement would report on a structure the instructions never
        # introduced. This also makes tiers 2 and 3 inherit the 'all'-period rejection
        # above for free.
        for flag in ("disclose_card_years", "disclose_insiders_fixed"):
            if getattr(self.rules, flag) and not self.rules.disclose_structure:
                raise ValueError(
                    f"{flag} is a higher rung of the disclosure ladder and writes into the "
                    f"section disclose_structure creates; set disclose_structure: true as "
                    f"well, or drop {flag}")
        # disclose_card_years announces the card condition of every year, which includes
        # the direction announce_no_info_period governs. Asking for silence and for an
        # announcement at once has no right answer, and the winner would be invisible in
        # the log — the class of bug runs/README.md records twice.
        if self.rules.disclose_card_years and self.rules.announce_no_info_period is False:
            raise ValueError(
                "disclose_card_years announces the card condition of EVERY year, including "
                "the years in which no lettered card is handed out; announce_no_info_period: "
                "false contradicts it — leave announce_no_info_period unset")
        # Market 1's clue is a ten-draw sample from one of two boxes of chips. Either box
        # can produce any row, so "never wrong" would be false, and it would hand that
        # market's agents the one thing it exists to withhold.
        if self.rules.clue_is_certain and self.market_spec.imperfect:
            raise ValueError(
                f"clue_is_certain states that a clue card carrying a letter is never wrong; "
                f"market {self.market}'s clue is a row of marks that either box can "
                f"produce, so the wording would be false")
        if self.rules.period_end_style == "memo":
            # The memo is cumulative: each version is a rewrite of the one before it, so
            # carrying two hands the agent a superseded copy of its own conclusions
            # alongside the current one. It is also expensive in the wrong place — notes
            # ride in the user message, which no prefix cache covers, and they appear in
            # ~96% of turn and broadcast calls.
            if self.rules.period_end_notes != 1:
                raise ValueError(
                    f"period_end_style 'memo' rewrites one standing document, so exactly "
                    f"one is carried forward; period_end_notes is "
                    f"{self.rules.period_end_notes} — set it to 1")
            # Reasoning shares the reflect budget with the note. At 3,000 and a 100-word
            # ask, 3% of year-end notes already come back empty having spent the lot
            # thinking, and one came back truncated mid-clause. A 500-800 word memo is
            # ~1,100 tokens of body before any reasoning, so 3,000 would truncate it as a
            # matter of course — and a truncated memo is the seat's whole memory.
            floor = 4096
            for a in self.agents:
                if a.kind == "llm" and a.reflect_max_output_tokens < floor:
                    raise ValueError(
                        f"period_end_style 'memo' asks for {self.rules.memo_words[0]}-"
                        f"{self.rules.memo_words[1]} words, which is ~1,100 output tokens "
                        f"before the reasoning that shares the same budget; "
                        f"reflect_max_output_tokens is {a.reflect_max_output_tokens}, "
                        f"below the {floor} floor — the memo would be truncated and stored "
                        f"anyway")
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
