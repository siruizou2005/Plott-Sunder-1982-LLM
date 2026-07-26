/**
 * Cutting the event stream into TURNS.
 *
 * The log is a flat list of events, but the experiment's process is nested:
 *
 *     Session -> Period(12) -> Round(<=3) -> Turn(12 seats) -> decide / broadcast / settle
 *
 * A viewer that steps event by event tears a single turn apart — the decision lands on one
 * step and the broadcast it triggered on the next — so this module folds events back into
 * the unit a human actually reasons about. It is the ONLY definition of a step; the server
 * computes it once and ships it to the browser, which is why there is no matching rule in
 * web/src/.
 *
 * The rule, and why it is shaped this way:
 *
 *   - Structural events stand alone and force any open turn shut.
 *   - A turn opens on `brief`, which the engine emits per actor per turn — but ONLY for llm
 *     agents (engine.py run_turn). Scripted runs have no briefs, so `agent_view` opens one
 *     too, guarded on the seat changing so it does not re-open the turn its own brief just
 *     started.
 *   - Sub-steps skip `model_turn` and `book`: the former is API plumbing that belongs in the
 *     trail's collapsed section, the latter a snapshot with no narrative moment of its own.
 *
 * Checked against all four logs on disk: the turn count equals the `action` count exactly
 * (24 / 432 / 432 / 432), which is the invariant that matters — one turn, one decision.
 */

const STRUCT = {
  session_start: 'session_open',
  period_start: 'period_open',
  round_start: 'round_open',
  period_end: 'period_close',
  session_end: 'session_close',
}

/** Events that ride along inside a turn without being worth stopping on. */
const NOT_A_SUBSTEP = new Set(['model_turn', 'book'])

export function buildTimeline(events) {
  const out = []
  let cur = null          // the turn being filled
  let openSeat = null     // whose turn is open, so agent_view can tell "same actor" apart
  let order = []          // this round's speaking order, from round_start
  let period = 0
  let round = 0

  const push = (t) => {
    out.push(t)
    return t
  }

  events.forEach((e, i) => {
    const kind = STRUCT[e.type]
    if (kind) {
      cur = null
      openSeat = null
      if (e.type === 'period_start') { period = e.payload?.period ?? period; round = 0 }
      if (e.type === 'round_start') {
        round = e.payload?.round ?? round
        order = e.payload?.order ?? []
      }
      push({ kind, period, round, seq: 0, seat: null, from: i, to: i, subs: [i] })
      return
    }

    const opensTurn = e.type === 'brief' || (e.type === 'agent_view' && openSeat !== e.seat)
    if (opensTurn) {
      openSeat = e.seat
      cur = push({
        kind: 'turn',
        period, round,
        seq: order.indexOf(e.seat) + 1,   // 0 when the order is unknown
        seat: e.seat,
        from: i, to: i, subs: [],
      })
    } else if (cur === null) {
      // No turn is open and this is not structural. In practice this is the batch of 12
      // period-end reflections (which follow `period_end`) and the empty book snapshot that
      // follows `period_start`. Both get a provisional group; the empty one is folded back
      // into the preceding structural step at the end.
      cur = push({
        kind: 'period_reflect',
        period, round, seq: 0, seat: null,
        from: i, to: i, subs: [],
      })
      openSeat = null
    }

    cur.to = i
    if (!NOT_A_SUBSTEP.has(e.type)) cur.subs.push(i)
  })

  // Drop the sub-step-less orphans (the post-period_start book snapshot), extending the
  // step before them so no event falls outside the timeline.
  const kept = []
  for (const t of out) {
    if (t.kind === 'period_reflect' && t.subs.length === 0) {
      if (kept.length) kept[kept.length - 1].to = t.to
      continue
    }
    kept.push(t)
  }
  return kept
}

/**
 * Where each period begins, for the period-jump chips: period number -> step index.
 * Keyed off `period_open` so a chip lands on the period's own header, not mid-round.
 */
export function periodIndex(timeline) {
  const out = []
  timeline.forEach((t, i) => {
    if (t.kind === 'period_open') out.push({ period: t.period, step: i })
  })
  return out
}
