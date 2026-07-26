import { infoLabel, reasonLabel, stepKindLabel, useT, type Strings } from '../i18n'
import { useStore, type DerivedState } from '../store'
import { splitTurn } from '../turn'
import { TYPE_COLOR } from '../types'
import { Tag } from './ui'

/**
 * The one line that answers "where am I and what just happened".
 *
 * Shown on both the market tab and the trail tab so switching between them never loses the
 * thread — that is the whole reason it lives outside either view.
 */
export function TurnHeader({ d }: { d: DerivedState }) {
  const t = useT()
  const meta = useStore((s) => s.meta)
  const turn = d.turn
  if (!turn) return null

  const maxRounds = meta?.config?.max_rounds_per_period ?? 3
  const nSeats = d.order.length || 12
  const nPeriods = meta?.sequence?.states?.length ?? 12

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-slate-200
                    bg-white px-4 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-900">
      <span className="tabular-nums font-semibold text-slate-700 dark:text-slate-200">
        {t.period} {d.period || '—'}
        <span className="ml-0.5 font-normal text-slate-400">/{nPeriods}</span>
      </span>

      {/* The realized dividend is the experiment's hidden variable — label it every time it
          appears so nobody reads the viewer as if the agents could see it too. */}
      {d.state && (
        <Tag tone={d.state === 'X' ? 'blue' : 'amber'} title={t.audienceOnly}>
          {d.state} · {t.audienceOnly}
        </Tag>
      )}
      <Tag tone={d.info === 'insider' ? 'amber' : d.info === 'all' ? 'red' : 'slate'}>
        {infoLabel(t, d.info)}
      </Tag>

      <span className="tabular-nums text-slate-500 dark:text-slate-400">
        {t.round} {d.round || '—'}<span className="text-slate-400">/{maxRounds}</span>
      </span>
      {turn.kind === 'turn' && turn.seq > 0 && (
        <span className="tabular-nums text-slate-500 dark:text-slate-400">
          {t.turnLabel} {turn.seq}<span className="text-slate-400">/{nSeats}</span>
        </span>
      )}

      <span className="mx-1 h-3 w-px bg-slate-200 dark:bg-slate-700" />
      <Narrative d={d} t={t} />
    </div>
  )
}

function Narrative({ d, t }: { d: DerivedState; t: Strings }) {
  const turn = d.turn!
  if (turn.kind !== 'turn') {
    return (
      <span className="font-medium text-slate-600 dark:text-slate-300">
        {stepKindLabel(t, turn.kind)}
        {turn.kind === 'period_reflect' && (
          <span className="ml-2 font-normal text-slate-400">{t.periodReflections}</span>
        )}
      </span>
    )
  }

  const seat = turn.seat!
  const st = d.seats[seat]
  const p = splitTurn(d.turnEvents, seat)
  const a = p.action?.payload
  const v = p.violations[0]?.payload
  const b = p.broadcast?.payload

  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <span className="font-semibold text-slate-800 dark:text-slate-100">▸ {seat}</span>
      {st?.type && (
        <span className="inline-flex items-center gap-1 text-slate-500 dark:text-slate-400">
          <span className="inline-block h-2 w-2 rounded-full"
                style={{ background: TYPE_COLOR[st.type] ?? '#94a3b8' }} />
          {st.type}
        </span>
      )}
      {st && (st.card
        ? <Tag tone={st.card === 'X' ? 'blue' : 'amber'}>{st.card} · {t.insiderBadge}</Tag>
        : <span className="text-slate-300 dark:text-slate-600">{t.blank}</span>)}

      {a && a.action !== 'no_quote' ? (
        <>
          <span className="text-slate-300">·</span>
          {a.action === 'accept_standing' && <span className="text-slate-400">↩</span>}
          <Tag tone={a.side === 'bid' ? 'green' : 'red'}>{a.side === 'bid' ? t.bid : t.ask}</Tag>
          <span className="tabular-nums font-semibold">{a.price}</span>
        </>
      ) : (
        <>
          <span className="text-slate-300">·</span>
          <span className="text-slate-400">
            {v ? `${t.violation}: ${reasonLabel(t, v.reason)}` : t.noQuote}
          </span>
        </>
      )}

      {b && (
        <>
          <span className="text-slate-300">→</span>
          <span className="tabular-nums text-slate-500 dark:text-slate-400">
            {t.broadcastTo} {b.recipients?.length ?? 0} · {t.accepted} {b.n_accept ?? 0}
          </span>
        </>
      )}

      {p.trades.length > 0 && (
        <>
          <span className="text-slate-300">→</span>
          <span className="font-medium text-emerald-700 dark:text-emerald-400">
            {t.traded} {p.trades[0].payload.seller} → {p.trades[0].payload.buyer}
            {' @ '}<span className="tabular-nums">{p.trades[0].payload.price}</span>
          </span>
        </>
      )}
      {!p.trades.length && a?.outcome === 'posted' && (
        <>
          <span className="text-slate-300">→</span>
          <span className="text-slate-500 dark:text-slate-400">{t.posted}</span>
        </>
      )}
    </span>
  )
}
