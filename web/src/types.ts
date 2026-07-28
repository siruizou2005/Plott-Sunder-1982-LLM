export type Side = 'bid' | 'ask'
export type InfoCond = 'none' | 'insider' | 'all'

/**
 * The three `model_turn` fields the server does NOT push with the bulk event stream.
 *
 * They are 90.6% of a log's bytes (`user` 33.6%, `system` 30.9%, `reasoning` 26.1% on
 * runs/rounds/m4_r5_random) and are rendered only inside the raw-record panel, which is
 * collapsed three levels deep. A `model_turn` whose payload carries `detail: true` has them
 * on disk; opening the panel fetches them by event index. `completion` is not here — it is
 * 0.8% of the file and shows in the collapsed summary line, so it always ships.
 */
export interface TurnDetail {
  system?: string
  user?: string
  reasoning?: string
}

/** One line of the JSONL log, unchanged from what the Python engine wrote. */
export interface Ev {
  event_id: number
  session: number
  period: number
  round: number
  type: string
  seat: string | null
  agent_visible: boolean
  payload: any
  ts: string
}

export interface QuoteT { seat: string; side: Side; price: number; posted_at?: number }
export interface BookT { bid: QuoteT | null; ask: QuoteT | null; spread: number | null }

/**
 * One step of the timeline, computed server-side in web/server/timeline.js. A step is a
 * TURN — everything one agent did and everything that happened because of it — not a
 * single event, which is what made a turn impossible to read whole.
 */
export type TurnKind =
  | 'turn' | 'session_open' | 'period_open' | 'round_open'
  | 'period_close' | 'period_reflect' | 'session_close'

export interface Turn {
  kind: TurnKind
  period: number
  round: number
  /** The seat's position in this round's speaking order, 1-based; 0 when unknown. */
  seq: number
  seat: string | null
  /** Inclusive event-index range this step covers. */
  from: number
  to: number
  /** Event indices worth stopping on inside the turn (excludes model_turn / book). */
  subs: number[]
}

export interface PeriodMark { period: number; step: number }

export interface SeatState {
  seat: string
  type: string
  certs: number
  cash: number
  card: string | null
  cumulative: number
  lastProfit: number | null
  /** Fixed for the whole session and never visible to any agent — audience-only. */
  insider: boolean
}

/** What a seat did in the current round, for the round strip. */
export type RoundOutcome = 'traded' | 'posted' | 'no_quote' | 'violation'

export interface TradeT {
  buyer: string; seller: string; price: number; trigger: string
  global_seq: number; period: number
}

export interface RunInfo {
  runId: string
  name: string
  /** Subdirectory the run sits in — 'm3', 'baselines', … — or null for a flat run. */
  group: string | null
  stamp: string
  bytes: number
  mtime: number
  hasMetrics: boolean
  sequence: string | null
  agentKinds: string[]
  sessions: number | null
  totals: { calls: number; cost_usd: number; wall_clock_s: number } | null
}

/** The seat colours: one hue family per dividend type, so the visualisation reads as one
 *  system. Type I is the high-X type, type III the high-Y type. */
export const TYPE_COLOR: Record<string, string> = {
  I: '#4f7cff',
  II: '#8b5cf6',
  III: '#e0803c',
}

export const STATE_TINT: Record<string, string> = {
  X: 'rgba(79,124,255,0.10)',
  Y: 'rgba(224,128,60,0.10)',
  // Market 5 is the three-state market. Without a Z its periods drew untinted and were
  // absent from the legend, so a third of that market read as "no state".
  Z: 'rgba(16,185,129,0.10)',
}

/** The same hues at chip strength, for the period-jump buttons. */
export const STATE_TINT_SOLID: Record<string, string> = {
  X: 'rgba(79,124,255,0.28)',
  Y: 'rgba(224,128,60,0.28)',
  Z: 'rgba(16,185,129,0.28)',
}
