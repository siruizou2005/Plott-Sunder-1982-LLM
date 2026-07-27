import { create } from 'zustand'
import type { BookT, Ev, PeriodMark, RoundOutcome, RunInfo, SeatState, TradeT, Turn }
  from './types'
import type { Lang } from './i18n'

/**
 * The whole client state.
 *
 * The browser holds every event and derives the market state by folding events up to the
 * cursor. That keeps replay and live-follow identical: the server only ever says "here are
 * more events" and "the cursor is here".
 *
 * The cursor has two levels. `cursor` indexes the TURN timeline the server computed in
 * web/server/timeline.js; `sub` indexes the events inside that turn. The client never
 * recomputes the timeline — one definition of a step, living on the server.
 */

function initialLang(): Lang {
  const q = new URLSearchParams(location.search).get('lang')
  if (q === 'zh' || q === 'en') return q
  const v = localStorage.getItem('ps1982_lang')
  if (v === 'zh' || v === 'en') return v
  return 'zh'
}

export interface DerivedState {
  period: number
  round: number
  info: string
  state: string | null
  cards: Record<string, string | null>
  book: BookT
  seats: Record<string, SeatState>
  trades: TradeT[]
  marketLog: any[]
  /** Highest market-action sequence number reached, for quote age. */
  actionSeq: number

  /** The step the cursor sits on, and every event it covers, in order. */
  turn: Turn | null
  turnEvents: Ev[]
  /** Absolute event index of the current sub-step — drives the trail's section highlight. */
  subEventIndex: number
  focusSeat: string | null

  /** This round's speaking order and how far through it we are. */
  order: string[]
  nextSeat: string | null
  roundOutcomes: Record<string, RoundOutcome>
}

interface Store {
  lang: Lang
  setLang: (l: Lang) => void
  tab: string
  setTab: (t: string) => void

  connected: boolean
  runs: RunInfo[]
  current: string | null
  runId: string | null
  meta: any
  metrics: any
  live: boolean
  seatTypes: Record<string, string>
  theory: Theory

  events: Ev[]
  timeline: Turn[]
  periods: PeriodMark[]
  cursor: number
  sub: number
  playing: boolean
  speed: number
  error: string | null

  connect: () => void
  send: (m: any) => void
  load: (runId: string) => void
  play: () => void
  pause: () => void
  stepTurn: (n: number) => void
  stepSub: (n: number) => void
  seek: (c: number, sub?: number) => void
  setSpeed: (s: number) => void
}

let ws: WebSocket | null = null

/**
 * Seat -> dividend type.
 *
 * `session_start` carries the whole map, so normally this is known from the very first
 * event. The settlement events are a fallback for a log that somehow lacks it — they name
 * each seat's type too, and types are fixed for a session, so a later event is a valid
 * source for an earlier one. Nothing leaks either way: the grid already says that types
 * and clue cards are audience-visible and no agent ever sees them.
 */
/** RE/PI predictions the RUN recorded. Market 3's values used to be hard-coded in
 *  MarketView, which made the viewer silently wrong for any other market.
 *
 *  Two key schemes live here, and which one a log uses is a fact about when it was written:
 *   - PERIOD-keyed ("1", "2", ...) — what the engine writes now, and the only scheme that
 *     can express market 1, whose prediction depends on the ten-draw sample that period
 *     drew. `insider|Y` is RE 320 in period 5 and RE 262 in period 8.
 *   - (info|state)-keyed — every log written before that. Correct for markets 2-5, where
 *     the clue is a letter; wrong for market 1, which is why the engine now refuses to
 *     write that form for an imperfect market at all.
 *  `theoryFor` reads either, preferring the period. */
export type TheoryCell = { PI: number; RE: number; holder?: { PI: string; RE: string } }
export type Theory = Record<string, TheoryCell>

/** The prediction for one period, from whichever scheme this run recorded. */
export function theoryFor(theory: Theory, period: number,
                          info: string | null, state: string | null): TheoryCell | undefined {
  const byPeriod = theory[String(period)]
  if (byPeriod) return byPeriod
  // The (info|state) fallback needs both; a bucket that has neither predates the fields.
  return info && state ? theory[`${info}|${state}`] : undefined
}

/** Logs written before the engine recorded its theory are market 3 — the only market that
 *  existed then — so this is a fact about those logs, not a guess about new ones. */
export const THEORY_MARKET3: Theory = {
  'none|X': { PI: 220, RE: 220, holder: { PI: 'I', RE: 'I' } },
  'none|Y': { PI: 220, RE: 220, holder: { PI: 'I', RE: 'I' } },
  'insider|X': { PI: 400, RE: 400, holder: { PI: 'I_insider', RE: 'I' } },
  'insider|Y': { PI: 220, RE: 175, holder: { PI: 'I_uninformed', RE: 'III' } },
  'all|X': { PI: 400, RE: 400, holder: { PI: 'I', RE: 'I' } },
  'all|Y': { PI: 175, RE: 175, holder: { PI: 'III', RE: 'III' } },
}

/** Market 1's clue is a ten-draw sample, so an (info|state) cell cannot hold its
 *  prediction — `insider|Y` is RE 320 in period 5 and RE 262 in period 8. Logs written
 *  before the engine keyed by period carry the state-contingent value there (RE 350),
 *  which is wrong for every one of those periods. Drawing no theory line is the honest
 *  outcome; the engine now refuses to write that field for an imperfect market at all. */
const stateKeyed = (th: Theory) => Object.keys(th).some((k) => k.includes('|'))

function harvestTheory(batch: Ev[], into: Theory): Theory {
  let out = into
  let market: number | undefined
  for (const e of batch) {
    if (e.type === 'session_start' && e.payload?.market !== undefined) market = e.payload.market
    if (e.type === 'session_start' && e.payload?.theory) {
      const th = e.payload.theory as Theory
      out = market === 1 && stateKeyed(th) ? {} : th
    }
    // period_start carries the prediction for its own period, computed from the clue that
    // period actually dealt. It is the authoritative source when both are present, and it
    // is the only one a resumed log is guaranteed to have.
    if (e.type === 'period_start' && e.payload?.theory && e.payload?.period !== undefined) {
      out = { ...out, [String(e.payload.period)]: e.payload.theory as TheoryCell }
    }
  }
  return out
}

function harvestSeatTypes(batch: Ev[], into: Record<string, string>): Record<string, string> {
  let found: Record<string, string> | null = null
  for (const e of batch) {
    if (e.type === 'session_start' && e.payload?.seat_types) {
      found = { ...(found ?? into), ...e.payload.seat_types }
      continue
    }
    const rows = e.type === 'period_end' ? e.payload?.results
      : e.type === 'session_end' ? e.payload?.totals
        : null
    if (!rows) continue
    for (const [seat, r] of Object.entries<any>(rows)) {
      if (r?.type && (found ?? into)[seat] !== r.type) (found ??= { ...into })[seat] = r.type
    }
  }
  return found ?? into
}

export const useStore = create<Store>((set, get) => ({
  lang: initialLang(),
  setLang: (l) => { localStorage.setItem('ps1982_lang', l); set({ lang: l }) },
  tab: 'market',
  setTab: (t) => set({ tab: t }),

  connected: false,
  runs: [],
  current: null,
  runId: null,
  meta: null,
  metrics: null,
  live: false,
  seatTypes: {},
  theory: THEORY_MARKET3,

  events: [],
  timeline: [],
  periods: [],
  cursor: 0,
  sub: 0,
  playing: false,
  speed: 1,
  error: null,

  connect: () => {
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`
    ws = new WebSocket(url)
    ws.onopen = () => set({ connected: true, error: null })
    ws.onclose = () => {
      set({ connected: false })
      setTimeout(() => get().connect(), 1500)
    }
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data)
      switch (m.type) {
        case 'hello': {
          set({ runs: m.runs, current: m.current })
          if (get().runId || !m.runs.length) break
          // ?run=<name>/<stamp> or ?run=<name> opens a specific run — handy for sharing a
          // link to one. Otherwise open the live run, else the newest.
          const want = new URLSearchParams(location.search).get('run')
          const match = want && (m.runs.find((r: RunInfo) => r.runId === want)
                              ?? m.runs.find((r: RunInfo) => r.name === want))
          get().load(match?.runId ?? m.current ?? m.runs[0].runId)
          break
        }
        case 'loaded':
          set({
            runId: m.runId, meta: m.meta, metrics: m.metrics, live: m.live,
            events: [], timeline: m.timeline ?? [], periods: m.periods ?? [],
            cursor: 0, sub: 0, seatTypes: {}, theory: THEORY_MARKET3,
          })
          break
        case 'events':
          set({
            events: get().events.concat(m.events),
            seatTypes: harvestSeatTypes(m.events, get().seatTypes),
            theory: harvestTheory(m.events, get().theory),
          })
          break
        case 'ready':
          set({ cursor: m.cursor ?? 0, sub: m.sub ?? 0 })
          break
        case 'grew':
          set({ timeline: m.timeline ?? get().timeline, periods: m.periods ?? get().periods })
          // A live run grew; jump to the end so following shows the newest activity.
          if (get().live) {
            const last = Math.max(0, (m.timeline?.length ?? 1) - 1)
            get().seek(last)
          }
          break
        case 'cursor':
          set({ cursor: m.cursor, sub: m.sub ?? 0 })
          break
        case 'playing':
          set({ playing: m.playing })
          break
        case 'error':
          set({ error: m.message })
          break
      }
    }
  },

  send: (m) => { if (ws?.readyState === 1) ws.send(JSON.stringify(m)) },
  load: (runId) => { get().send({ type: 'load', runId }) },
  play: () => get().send({ type: 'play' }),
  pause: () => get().send({ type: 'pause' }),
  stepTurn: (n) => get().send({ type: 'step', n, unit: 'turn' }),
  stepSub: (n) => get().send({ type: 'step', n, unit: 'sub' }),
  seek: (c, sub = -1) => get().send({ type: 'seek', cursor: c, sub }),
  setSpeed: (s) => { set({ speed: s }); get().send({ type: 'speed', speed: s }) },
}))

const EMPTY_BOOK: BookT = { bid: null, ask: null, spread: null }

/** What each seat did so far in the round the cursor is in — drives the round strip. */
function roundOutcomes(events: Ev[], timeline: Turn[], cursor: number) {
  const cur = timeline[cursor]
  const out: Record<string, RoundOutcome> = {}
  if (!cur) return out
  for (let i = 0; i <= cursor && i < timeline.length; i++) {
    const t = timeline[i]
    if (t.kind !== 'turn' || !t.seat) continue
    if (t.period !== cur.period || t.round !== cur.round) continue
    let o: RoundOutcome = 'no_quote'
    for (let k = t.from; k <= t.to && k < events.length; k++) {
      const e = events[k]
      if (e.seat !== t.seat) continue
      if (e.type === 'action') {
        o = e.payload.action === 'no_quote' ? 'no_quote'
          : e.payload.outcome === 'posted' ? 'posted' : 'traded'
      } else if (e.type === 'violation' && o === 'no_quote') {
        o = 'violation'
      }
    }
    out[t.seat] = o
  }
  return out
}

/**
 * Fold every event up to the cursor into the market state.
 *
 * Recomputed from scratch on each cursor move rather than kept incrementally, because
 * scrubbing backwards has to be exact and a 12-period log is only a couple of thousand
 * events.
 */
export function derive(events: Ev[], timeline: Turn[], cursor: number, sub: number,
                       seatTypes: Record<string, string>): DerivedState {
  const turn = timeline[Math.min(cursor, timeline.length - 1)] ?? null
  const upto = turn ? (turn.subs[Math.min(sub, turn.subs.length - 1)] ?? turn.to) : -1

  const d: DerivedState = {
    period: 0, round: 0, info: 'none', state: null, cards: {},
    book: EMPTY_BOOK, seats: {}, trades: [], marketLog: [], actionSeq: 0,
    turn, turnEvents: [], subEventIndex: upto, focusSeat: turn?.seat ?? null,
    order: [], nextSeat: null, roundOutcomes: {},
  }
  const cum: Record<string, number> = {}
  const lastProfit: Record<string, number> = {}
  let insiders: string[] = []

  const blank = (seat: string): SeatState => ({
    seat, type: seatTypes[seat] ?? '', certs: 2, cash: 10000,
    card: d.cards[seat] ?? null, cumulative: cum[seat] ?? 0,
    lastProfit: lastProfit[seat] ?? null, insider: insiders.includes(seat),
  })

  const ensure = (seat: string): SeatState => (d.seats[seat] ??= blank(seat))

  for (let i = 0; i <= upto && i < events.length; i++) {
    const e = events[i]
    switch (e.type) {
      case 'period_start':
        d.period = e.payload.period
        d.state = e.payload.state
        d.info = e.payload.info
        d.cards = e.payload.cards ?? {}
        d.book = EMPTY_BOOK
        d.marketLog = []
        d.seats = {}
        d.actionSeq = 0
        d.order = []
        // Reset with everything else. Leaving it behind made a freshly opened period
        // display the PREVIOUS period's last round — "round 3/3" on a period that had not
        // begun its first.
        d.round = 0
        // The permanent insider roster. Audience-only: agents are never told how many
        // insiders there are, who they are, or that they are the same people every period.
        insiders = e.payload.fixed_insiders ?? insiders
        for (const seat of Object.keys(d.cards)) d.seats[seat] = blank(seat)
        break
      case 'round_start':
        d.round = e.payload.round
        d.order = e.payload.order ?? []
        break
      case 'book':
        d.book = e.payload
        break
      case 'action':
        if (e.payload.action !== 'no_quote' && e.payload.seq !== undefined) {
          d.actionSeq = Math.max(d.actionSeq, e.payload.seq)
          if (e.payload.outcome === 'posted') {
            for (let k = d.marketLog.length - 1; k >= 0; k--) {
              if (d.marketLog[k].side === e.payload.side && d.marketLog[k].outcome === 'posted') {
                d.marketLog[k] = { ...d.marketLog[k], outcome: 'superseded' }
                break
              }
            }
          }
          d.marketLog.push({
            seq: e.payload.seq, seat: e.seat, side: e.payload.side,
            action: e.payload.action, round: e.round,
            price: e.payload.settled_at ?? e.payload.price,
            outcome: e.payload.outcome, counterparty: e.payload.counterparty ?? null,
            // Buyer and seller are recorded explicitly: accepting a standing BID means
            // the acceptor SOLD, so the quote's side alone reads backwards.
            buyer: e.payload.buyer ?? null, seller: e.payload.seller ?? null,
          })
        }
        break
      case 'trade': {
        const p = e.payload
        d.trades.push({ ...p, period: e.period })
        const b = ensure(p.buyer), s = ensure(p.seller)
        b.certs = p.buyer_after?.certs ?? b.certs + 1
        b.cash = p.buyer_after?.cash ?? b.cash - p.price
        s.certs = p.seller_after?.certs ?? s.certs - 1
        s.cash = p.seller_after?.cash ?? s.cash + p.price
        break
      }
      case 'period_end':
        for (const [seat, r] of Object.entries<any>(e.payload.results ?? {})) {
          cum[seat] = r.cumulative
          lastProfit[seat] = r.profit
          const st = ensure(seat)
          st.certs = r.certs
          st.cumulative = r.cumulative
          st.lastProfit = r.profit
          st.type = r.type ?? st.type
          if (r.insider !== undefined) st.insider = r.insider
        }
        break
    }
  }

  if (turn) {
    d.turnEvents = events.slice(turn.from, Math.min(turn.to + 1, events.length))
    d.focusSeat = turn.seat ?? d.turnEvents.find((f) => f.seat)?.seat ?? null
    d.roundOutcomes = roundOutcomes(events, timeline, cursor)
    // `seq` is this seat's 1-based position in the round, so index `seq` is whoever speaks
    // next — undefined at the end of a round, which is itself worth showing.
    if (turn.kind === 'turn' && turn.seq > 0) d.nextSeat = d.order[turn.seq] ?? null
  }
  return d
}
