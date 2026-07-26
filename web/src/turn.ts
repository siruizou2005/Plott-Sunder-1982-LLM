import type { Ev } from './types'

/**
 * One turn's events, sorted into the roles the UI actually talks about.
 *
 * The header and the trail both read from here so they can never disagree about what
 * happened in a turn — the header's one-line summary is a compression of exactly the
 * sections the trail renders.
 *
 * Note which events belong to WHOM. A turn contains the actor's own events, but also the
 * broadcast replies of up to eleven other seats and, after a trade, the counterparty's
 * note to self. So anything shown per-seat has to be filtered by seat rather than assumed
 * to belong to the actor.
 */
export interface TurnParts {
  brief: Ev | null
  view: Ev | null
  action: Ev | null
  broadcast: Ev | null
  trades: Ev[]
  /** Only the actor's own rejected attempts; a malformed broadcast reply is not one. */
  violations: Ev[]
  reflections: Ev[]
  modelCalls: Ev[]
}

export function splitTurn(evs: Ev[], seat: string | null): TurnParts {
  const p: TurnParts = {
    brief: null, view: null, action: null, broadcast: null,
    trades: [], violations: [], reflections: [], modelCalls: [],
  }
  for (const e of evs) {
    switch (e.type) {
      case 'brief': p.brief ??= e; break
      case 'agent_view': p.view ??= e; break
      case 'action': p.action ??= e; break
      case 'broadcast': p.broadcast ??= e; break
      case 'trade': p.trades.push(e); break
      case 'reflection': p.reflections.push(e); break
      case 'model_turn': p.modelCalls.push(e); break
      case 'violation':
        // stale_quote names the POSTER, not the actor — it is someone else's quote dying,
        // not this agent's attempt being refused.
        if (e.seat === seat && e.payload?.reason !== 'stale_quote') p.violations.push(e)
        break
    }
  }
  return p
}

/** Total tokens and wall time the turn cost, for the raw-record header. */
export function turnCost(calls: Ev[]) {
  let tokens = 0, seconds = 0
  for (const c of calls) {
    tokens += (c.payload?.usage?.prompt_tokens ?? 0) + (c.payload?.usage?.completion_tokens ?? 0)
    seconds += c.payload?.latency_s ?? 0
  }
  return { calls: calls.length, tokens, seconds }
}

/**
 * A broadcast respondent's real standing.
 *
 * `winner` and `losers` come straight from the engine, but an agent can say "accept" and
 * still be absent from both: engine.py re-checks every acceptor with `_can_take` and drops
 * anyone who can no longer pay or deliver. Those never entered the random draw, so calling
 * them "losers" misstates what happened to them.
 */
export type Standing = 'winner' | 'loser' | 'unable' | 'declined'

export function standingOf(r: any, payload: any): Standing {
  if (r.response !== 'accept') return 'declined'
  if (r.seat === payload.winner) return 'winner'
  return (payload.losers ?? []).includes(r.seat) ? 'loser' : 'unable'
}
