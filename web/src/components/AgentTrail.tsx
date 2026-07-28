import { basisLabel, infoLabel, reasonLabel, stepKindLabel, useT, type Strings } from '../i18n'
import { useStore, type DerivedState } from '../store'
import { splitTurn, standingOf, turnCost, type Standing } from '../turn'
import type { Ev } from '../types'
import { TYPE_COLOR } from '../types'
import { Empty, Panel, Tag, fmt } from './ui'

/** Table 2, market 3: francs paid per certificate if X / if Y. Audience-only. */
const DIVIDENDS: Record<string, [number, number]> = {
  I: [400, 100], II: [300, 150], III: [125, 175],
}

// ---------------------------------------------------------------- section frame

/**
 * One numbered step of the turn's story.
 *
 * Sections the sub-cursor has not reached yet are dimmed rather than hidden: the shape of
 * the turn — did it go to broadcast at all, was there a trade — should be visible before
 * you step into it.
 */
function Sec({ n, title, reached, current, children }: {
  n: string; title: string; reached: boolean; current: boolean; children: React.ReactNode
}) {
  return (
    <section className={`rounded-lg border bg-white shadow-sm transition
                         dark:bg-slate-900 ${
      current ? 'border-slate-900 ring-1 ring-slate-900 dark:border-slate-100 dark:ring-slate-100'
        : 'border-slate-200 dark:border-slate-700'} ${reached ? '' : 'opacity-40'}`}>
      <header className="flex items-baseline gap-2 border-b border-slate-200 px-3 py-2
                         dark:border-slate-700">
        <span className="text-sm font-semibold text-slate-400">{n}</span>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500
                       dark:text-slate-400">{title}</h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  )
}

function Fold({ label, children, className = '' }: {
  label: string; children: React.ReactNode; className?: string
}) {
  return (
    <details className={`group ${className}`}>
      <summary className="cursor-pointer select-none text-[11px] text-slate-500 underline
                          decoration-dotted underline-offset-2 hover:text-slate-700
                          dark:text-slate-400 dark:hover:text-slate-200">
        {label}
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  )
}

const Mono = ({ children, max = '20rem' }: { children: React.ReactNode; max?: string }) => (
  <pre style={{ maxHeight: max }}
       className="overflow-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-2
                  font-mono text-[11px] leading-relaxed text-slate-600 dark:bg-slate-950
                  dark:text-slate-300">{children}</pre>
)

// ---------------------------------------------------------------- ① what it saw

/** The briefing is written by ps1982/prompts/brief.py as `== TITLE ==` blocks. */
function briefBlocks(text: string) {
  const out: { title: string; body: string }[] = []
  let cur: { title: string; body: string[] } | null = null
  for (const ln of text.split('\n')) {
    const m = /^== (.+?) ==\s*$/.exec(ln)
    if (m) {
      if (cur) out.push({ title: cur.title, body: cur.body.join('\n').trim() })
      cur = { title: m[1], body: [] }
    } else if (cur) cur.body.push(ln)
  }
  if (cur) out.push({ title: cur.title, body: cur.body.join('\n').trim() })
  return out
}

function SawSection({ brief, d, t }: { brief: Ev | null; d: DerivedState; t: Strings }) {
  if (!brief) {
    // Scripted agents get no briefing (engine.py builds one only for kind == "llm"), so show
    // the same market facts from the folded state instead of an empty panel.
    return (
      <div className="space-y-1 text-xs text-slate-500 dark:text-slate-400">
        <p className="text-[11px] italic">{t.noBrief}</p>
        <p>
          {t.standingBid} {d.book.bid ? fmt(d.book.bid.price) : t.none}
          {' · '}{t.standingAsk} {d.book.ask ? fmt(d.book.ask.price) : t.none}
        </p>
        <p>{t.tradesThisYear} {d.marketLog.filter((e) => e.outcome !== 'posted').length}</p>
      </div>
    )
  }

  const blocks = briefBlocks(brief.payload.text ?? '')
  const find = (frag: string) => blocks.find((b) => b.title.includes(frag))
  const quotes = find('STANDING QUOTES')
  const record = find('PUBLIC RECORD')
  const notes = find('RECENT NOTES')
  const history = find('RECORD SO FAR')

  const recordLines = (record?.body ?? '').split('\n').filter((l) => l.trim())
  const dataLines = recordLines.slice(1)          // drop the column header
  const traded = dataLines.filter((l) => /traded/.test(l))

  return (
    <div className="space-y-2 text-xs">
      {quotes && (
        <div className="font-mono text-[11px] leading-relaxed text-slate-600 dark:text-slate-300">
          {quotes.body.split('\n').slice(0, 3).map((l, i) => <div key={i}>{l.trim()}</div>)}
        </div>
      )}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-500 dark:text-slate-400">
        <span>{t.tradesThisYear} <b className="tabular-nums text-slate-700
              dark:text-slate-200">{traded.length}</b></span>
        {traded.length > 0 && (
          <span className="font-mono text-[11px]">{t.lastTradeAt}: {traded[traded.length - 1].trim()}</span>
        )}
      </div>
      {notes?.body && (
        <Fold label={`${t.reflection} ▾`}>
          <Mono max="10rem">{notes.body}</Mono>
        </Fold>
      )}
      {history?.body && (
        <Fold label={`${t.yourRecord} ▾`}>
          <Mono max="10rem">{history.body}</Mono>
        </Fold>
      )}
      <Fold label={`${t.fullBrief} ▾`}>
        <Mono max="26rem">{brief.payload.text}</Mono>
      </Fold>
    </div>
  )
}

// ---------------------------------------------------------------- ② belief

function PosteriorBar({ p }: { p: { X: number; Y: number } }) {
  const x = Math.round((p.X ?? 0) * 100)
  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-sm">
        <div style={{ width: `${x}%`, background: '#4f7cff' }} />
        <div style={{ width: `${100 - x}%`, background: '#e0803c' }} />
      </div>
      <div className="mt-0.5 flex justify-between text-[10px] tabular-nums text-slate-500">
        <span>X {x}%</span><span>{100 - x}% Y</span>
      </div>
    </div>
  )
}

function ThoughtSection({ view, t }: { view: Ev | null; t: Strings }) {
  if (!view) return <p className="text-xs text-slate-400">—</p>
  const p = view.payload
  return (
    <div className="space-y-2">
      {p.posterior && <PosteriorBar p={p.posterior} />}
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <dt className="text-slate-400">{t.reservation} ({t.bid})</dt>
        <dd className="text-right tabular-nums font-medium">{fmt(p.reservation_buy)}</dd>
        <dt className="text-slate-400">{t.reservation} ({t.ask})</dt>
        <dd className="text-right tabular-nums font-medium">{fmt(p.reservation_sell)}</dd>
        <dt className="text-slate-400">{t.basis}</dt>
        <dd className="text-right"><Tag tone="violet">{basisLabel(t, p.basis)}</Tag></dd>
      </dl>
    </div>
  )
}

// ---------------------------------------------------------------- ③ action

function DidSection({ action, violations, t }: {
  action: Ev | null; violations: Ev[]; t: Strings
}) {
  const p = action?.payload
  const outcomeLabel: Record<string, string> = {
    posted: t.posted, traded: t.traded, crossed_auto: t.crossedAuto,
  }
  if (!p && !violations.length) return <p className="text-xs text-slate-400">{t.noAction}</p>

  return (
    <div className="space-y-2">
      {p && (
        <>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {p.action === 'no_quote' ? <Tag tone="slate">{t.noQuote}</Tag> : (
              <>
                <Tag tone={p.action === 'quote' ? 'blue' : 'violet'}>
                  {p.action === 'quote' ? t.quote : t.acceptStanding}
                </Tag>
                <Tag tone={p.side === 'bid' ? 'green' : 'red'}>
                  {p.side === 'bid' ? t.bid : t.ask}
                </Tag>
                <span className="tabular-nums text-lg font-semibold">{fmt(p.price)}</span>
                {p.settled_at !== undefined && p.settled_at !== p.price && (
                  <span className="text-xs text-slate-400">→ {fmt(p.settled_at)}</span>
                )}
              </>
            )}
          </div>
          {p.outcome && (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {t.outcome}: {outcomeLabel[p.outcome] ?? p.outcome}
              {p.counterparty ? ` · ${p.counterparty}` : ''}
            </p>
          )}
        </>
      )}
      {violations.map((v, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2 text-xs">
          <Tag tone="red">{t.violation}: {reasonLabel(t, v.payload.reason)}</Tag>
          {v.payload.side && <Tag tone="slate">{v.payload.side === 'bid' ? t.bid : t.ask}</Tag>}
          {v.payload.price != null && (
            <span className="tabular-nums font-medium">{fmt(v.payload.price)}</span>
          )}
          {v.payload.schema_errors?.length > 0 && (
            <Mono max="8rem">{v.payload.schema_errors.join('\n')}</Mono>
          )}
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------- ④ broadcast

const STANDING_STYLE: Record<Standing, string> = {
  winner: 'bg-emerald-600 text-white',
  loser: 'bg-emerald-100 text-emerald-800 line-through decoration-emerald-400 '
    + 'dark:bg-emerald-950 dark:text-emerald-300',
  unable: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300',
  declined: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
}

function ResponseSection({ broadcast, t }: { broadcast: Ev | null; t: Strings }) {
  if (!broadcast) return <p className="text-xs text-slate-400">{t.noBroadcast}</p>
  const p = broadcast.payload
  const responses: any[] = p.responses ?? []
  const label: Record<Standing, string> = {
    winner: t.winner, loser: t.losers, unable: t.couldNotSettle, declined: '',
  }
  const anyUnable = responses.some((r) => standingOf(r, p) === 'unable')

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-slate-500 dark:text-slate-400">
        {t.broadcastTo} {p.recipients?.length ?? 0} · {t.accepted} {p.n_accept ?? 0}
        {p.winner ? ` · ${t.winner} ${p.winner}` : ` · ${t.noAcceptor}`}
      </p>

      <div className="flex flex-wrap gap-1.5">
        {responses.map((r) => {
          const s = standingOf(r, p)
          return (
            <span key={r.seat} title={r.why ?? ''}
                  className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${STANDING_STYLE[s]}`}>
              {r.seat}{label[s] ? ` · ${label[s]}` : ''}
            </span>
          )
        })}
      </div>

      {p.losers?.length > 0 && (
        <p className="rounded bg-amber-50 p-2 text-[11px] leading-relaxed text-amber-900
                      dark:bg-amber-950/40 dark:text-amber-300">{t.losersNote}</p>
      )}
      {anyUnable && (
        <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
          {t.couldNotSettleNote}
        </p>
      )}

      {responses.some((r) => r.why) && (
        <Fold label={`${t.showReasons} ▾`}>
          <ul className="space-y-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            {responses.filter((r) => r.why).map((r) => (
              <li key={r.seat}>
                <span className="font-medium text-slate-600 dark:text-slate-300">{r.seat}</span>
                {' '}<span className={r.response === 'accept' ? 'text-emerald-600' : 'text-slate-400'}>
                  {r.response === 'accept' ? t.accepted : t.declined}
                </span>{' — '}{r.why}
              </li>
            ))}
          </ul>
        </Fold>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- ⑤ result

function ResultSection({ trades, reflections, t }: {
  trades: Ev[]; reflections: Ev[]; t: Strings
}) {
  if (!trades.length && !reflections.length) {
    return <p className="text-xs text-slate-400">—</p>
  }
  return (
    <div className="space-y-2">
      {trades.map((e, i) => {
        const p = e.payload
        return (
          <div key={i} className="text-sm">
            <span className="font-medium">{p.seller}</span>
            <span className="text-slate-400"> → </span>
            <span className="font-medium">{p.buyer}</span>
            <span className="text-slate-400"> @ </span>
            <span className="tabular-nums text-lg font-semibold">{fmt(p.price)}</span>
            <span className="ml-2 text-[11px] text-slate-400">{p.trigger}</span>
            {p.buyer_after && p.seller_after && (
              <div className="mt-0.5 text-[11px] tabular-nums text-slate-500 dark:text-slate-400">
                {p.buyer} {t.certs} {p.buyer_after.certs - 1}→{p.buyer_after.certs}
                {' · '}{t.cash} {fmt(p.buyer_after.cash + p.price)}→{fmt(p.buyer_after.cash)}
                {' | '}
                {p.seller} {t.certs} {p.seller_after.certs + 1}→{p.seller_after.certs}
                {' · '}{t.cash} {fmt(p.seller_after.cash - p.price)}→{fmt(p.seller_after.cash)}
              </div>
            )}
          </div>
        )
      })}
      {reflections.map((e, i) => (
        <div key={`r${i}`} className="rounded bg-slate-50 p-2 dark:bg-slate-950">
          <div className="mb-0.5 text-[10px] uppercase tracking-wide text-slate-400">
            {t.reflection} · {e.seat} · {e.payload.kind}
          </div>
          <p className="whitespace-pre-wrap text-[11px] leading-relaxed text-slate-600
                        dark:text-slate-300">{e.payload.text}</p>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------- raw record

/**
 * Every model call the turn made, collapsed.
 *
 * A broadcast turn makes twelve of these — one decision plus eleven replies — and rendering
 * them as raw JSON cards used to bury the actual decision under a screenful of plumbing.
 * The prompts stay available, because auditing exactly what a seat was sent is the point of
 * logging them; they just are no longer the first thing you see.
 */
function RawRecord({ calls, from, to, t }:
                   { calls: Ev[]; from: number; to: number; t: Strings }) {
  const askDetail = useStore((s) => s.askDetail)
  const details = useStore((s) => s.details)
  if (!calls.length) return null
  const { tokens, seconds } = turnCost(calls)
  return (
    <details className="rounded-lg border border-slate-200 bg-white shadow-sm
                        dark:border-slate-700 dark:bg-slate-900"
             // The prompts and reasoning are ~90% of a log and live only in here, so they
             // are fetched when this opens rather than shipped with every run.
             onToggle={(e) => { if (e.currentTarget.open) askDetail(from, to) }}>
      <summary className="cursor-pointer select-none px-3 py-2 text-xs font-semibold uppercase
                          tracking-wide text-slate-500 dark:text-slate-400">
        {t.rawRecord}
        <span className="ml-2 font-normal normal-case tabular-nums text-slate-400">
          {calls.length} {t.modelCalls} · {fmt(tokens)} {t.tokens} · {seconds.toFixed(1)}s
        </span>
      </summary>
      <div className="border-t border-slate-200 dark:border-slate-700">
        <div className="grid grid-cols-[4rem_7rem_1fr_auto] gap-2 border-b border-slate-100
                        px-3 py-1 text-[10px] uppercase tracking-wide text-slate-400
                        dark:border-slate-800">
          <span>{t.seat}</span><span>{t.purpose}</span><span>{t.completionLabel}</span>
          <span>{t.tokens} · {t.latency}</span>
        </div>
        {calls.map((c, i) => {
          const p = c.payload
          // `detail: true` means the server kept these three on disk. Until the fetch lands
          // the folds say so rather than rendering as empty, which would read as "this turn
          // had no prompt" — a claim about the data, not about the transfer.
          const d = details[c.event_id]
          const pending = p?.detail && !d
          const text = (k: 'system' | 'user' | 'reasoning') =>
            d?.[k] ?? (pending ? t.loadingDetail : p?.[k] ?? '')
          return (
            <details key={i} className="border-b border-slate-100 last:border-b-0
                                        dark:border-slate-800">
              <summary className="grid cursor-pointer select-none grid-cols-[4rem_7rem_1fr_auto]
                                  items-center gap-2 px-3 py-1.5 text-[11px]
                                  hover:bg-slate-50 dark:hover:bg-slate-800">
                <span className="font-medium text-slate-700 dark:text-slate-200">{c.seat}</span>
                <span className="text-slate-400">{p.purpose}</span>
                <span className="truncate font-mono text-slate-500 dark:text-slate-400">
                  {(p.completion || p.error || '').replace(/\s+/g, ' ').slice(0, 120)}
                </span>
                <span className="tabular-nums text-slate-400">
                  {(p.usage?.prompt_tokens ?? 0)}+{(p.usage?.completion_tokens ?? 0)}
                  {p.usage?.cache_hit_tokens ? ` · cache ${p.usage.cache_hit_tokens}` : ''}
                  {' · '}{p.latency_s}s
                </span>
              </summary>
              <div className="space-y-2 px-3 pb-3">
                <Fold label={`${t.systemPrompt} ▾`}><Mono max="14rem">{text('system')}</Mono></Fold>
                <Fold label={`${t.userPrompt} ▾`}><Mono max="14rem">{text('user')}</Mono></Fold>
                {/* The chain of thought — the only direct record of how the agent got to
                    its number, and the primary evidence for whether an uninformed seat
                    read the state off the price. Audience-only, like the clue cards.
                    `usage.reasoning_tokens` ships with the lite event, so a turn that did
                    reason still offers the fold before its text has arrived. */}
                {(d?.reasoning || (pending && p?.usage?.reasoning_tokens) || p?.reasoning) && (
                  <Fold label={`${t.reasoningLabel} ▾ ${p.usage?.reasoning_tokens ?? ''} ${t.tokens}`}>
                    <Mono max="18rem">{text('reasoning')}</Mono>
                  </Fold>
                )}
                <div>
                  <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-400">
                    {t.completionLabel}
                  </div>
                  <Mono max="14rem">{p.completion || p.error || '—'}</Mono>
                </div>
              </div>
            </details>
          )
        })}
      </div>
    </details>
  )
}

// ---------------------------------------------------------------- structural steps

function StructuralStep({ d, t }: { d: DerivedState; t: Strings }) {
  const turn = d.turn!
  const e = d.turnEvents[0]
  const reflections = d.turnEvents.filter((x) => x.type === 'reflection')

  if (turn.kind === 'period_reflect') {
    return (
      <Panel title={`${t.period} ${turn.period} — ${t.periodReflections}`}>
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          {reflections.map((r, i) => (
            <div key={i} className="rounded bg-slate-50 p-2 dark:bg-slate-950">
              <div className="mb-0.5 text-[10px] font-medium text-slate-500">{r.seat}</div>
              <p className="whitespace-pre-wrap text-[11px] leading-relaxed text-slate-600
                            dark:text-slate-300">{r.payload.text}</p>
            </div>
          ))}
        </div>
      </Panel>
    )
  }

  if (turn.kind === 'period_open' && e) {
    const cards: Record<string, string | null> = e.payload.cards ?? {}
    const insiders: string[] = e.payload.insiders ?? []
    return (
      <Panel title={`${t.kPeriodOpen} — ${t.period} ${e.payload.period}`}
             right={<Tag tone="violet">{t.audienceOnly}</Tag>}>
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
          <Tag tone={e.payload.state === 'X' ? 'blue' : 'amber'}>{e.payload.state}</Tag>
          <span className="text-slate-500">{infoLabel(t, e.payload.info)}</span>
        </div>
        <div className="flex flex-wrap gap-1">
          {Object.entries(cards).map(([seat, card]) => (
            <span key={seat}
                  className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
                    card ? 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300'
                      : 'bg-slate-100 text-slate-400 dark:bg-slate-800'}`}>
              {seat} {card ?? t.blank}{insiders.includes(seat) ? ' ◆' : ''}
            </span>
          ))}
        </div>
      </Panel>
    )
  }

  if (turn.kind === 'round_open' && e) {
    return (
      <Panel title={`${t.kRoundOpen} — ${t.round} ${e.payload.round}`}>
        <div className="flex flex-wrap gap-1">
          {(e.payload.order ?? []).map((seat: string, i: number) => (
            <span key={seat} className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px]
                                        tabular-nums text-slate-600 dark:bg-slate-800
                                        dark:text-slate-300">
              {i + 1}. {seat}
            </span>
          ))}
        </div>
      </Panel>
    )
  }

  if (turn.kind === 'period_close' && e) {
    const rows = Object.entries<any>(e.payload.results ?? {})
    return (
      <Panel title={`${t.kPeriodClose} — ${t.period} ${e.payload.period} · ${e.payload.state}`}>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wide text-slate-400">
              <th className="py-1">{t.seat}</th><th>{t.type}</th>
              <th className="text-right">{t.certs}</th>
              <th className="text-right">{t.profit}</th>
              <th className="text-right">{t.cumulative}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([seat, r]) => (
              <tr key={seat} className="border-t border-slate-100 dark:border-slate-800">
                <td className="py-0.5 font-medium">{seat}{r.insider ? ' ◆' : ''}</td>
                <td className="text-slate-500">{r.type}</td>
                <td className="text-right tabular-nums">{r.certs}</td>
                <td className={`text-right tabular-nums ${
                  r.profit >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{fmt(r.profit)}</td>
                <td className="text-right tabular-nums font-medium">{fmt(r.cumulative)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    )
  }

  return (
    <Panel title={stepKindLabel(t, turn.kind)}>
      <Mono max="30rem">{JSON.stringify(e?.payload ?? {}, null, 1).slice(0, 6000)}</Mono>
    </Panel>
  )
}

// ---------------------------------------------------------------- the turn page

export function AgentTrail({ d }: { d: DerivedState }) {
  const t = useT()
  if (!d.turn || !d.turnEvents.length) return <Empty>{t.waiting}</Empty>
  if (d.turn.kind !== 'turn') return <StructuralStep d={d} t={t} />

  const turn = d.turn
  const seat = turn.seat!
  const st = d.seats[seat]
  const p = splitTurn(d.turnEvents, seat)

  // Absolute event index of a part, so a section knows whether the sub-cursor has reached it.
  const at = (e: Ev | null | undefined) =>
    e ? turn.from + d.turnEvents.indexOf(e) : Number.POSITIVE_INFINITY
  const reached = (e: Ev | null | undefined) => at(e) <= d.subEventIndex
  const current = (...es: (Ev | null | undefined)[]) => es.some((e) => at(e) === d.subEventIndex)

  const div = DIVIDENDS[st?.type ?? '']
  const resultEvents = [...p.trades, ...p.reflections]

  return (
    <div className="space-y-3">
      {/* Identity once, at the top — not repeated in every panel title. */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border
                      border-slate-200 bg-white px-3 py-2 text-xs shadow-sm
                      dark:border-slate-700 dark:bg-slate-900">
        <span className="text-base font-semibold text-slate-800 dark:text-slate-100">{seat}</span>
        {st?.type && (
          <span className="inline-flex items-center gap-1 text-slate-500 dark:text-slate-400">
            <span className="inline-block h-2 w-2 rounded-full"
                  style={{ background: TYPE_COLOR[st.type] }} />
            {st.type}
            {div && <span className="tabular-nums text-slate-400"
                          title={`X / Y`}>({div[0]}/{div[1]})</span>}
          </span>
        )}
        {st && (st.card
          ? <Tag tone={st.card === 'X' ? 'blue' : 'amber'}>{st.card} · {t.insiderBadge}</Tag>
          : <span className="text-slate-300 dark:text-slate-600">{t.card}: {t.blank}</span>)}
        {st?.insider && <Tag tone="violet" title={t.audienceOnly}>◆ {t.audienceOnly}</Tag>}
        <span className="ml-auto flex gap-3 tabular-nums text-slate-500 dark:text-slate-400">
          <span>{t.certs} <b className="text-slate-700 dark:text-slate-200">{st?.certs ?? '—'}</b></span>
          <span>{t.cash} <b className="text-slate-700 dark:text-slate-200">{fmt(st?.cash)}</b></span>
          <span>{t.cumulative} <b className="text-slate-700 dark:text-slate-200">
            {fmt(st?.cumulative)}</b></span>
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <Sec n="①" title={t.secSaw} reached={reached(p.brief) || !p.brief}
             current={current(p.brief)}>
          <SawSection brief={p.brief} d={d} t={t} />
        </Sec>
        <Sec n="②" title={t.secThought} reached={reached(p.view)} current={current(p.view)}>
          <ThoughtSection view={p.view} t={t} />
        </Sec>
        <Sec n="③" title={t.secDid}
             reached={reached(p.action) || p.violations.some(reached)}
             current={current(p.action, ...p.violations)}>
          <DidSection action={p.action} violations={p.violations} t={t} />
        </Sec>
      </div>

      <Sec n="④" title={t.secResponse} reached={reached(p.broadcast) || !p.broadcast}
           current={current(p.broadcast)}>
        <ResponseSection broadcast={p.broadcast} t={t} />
      </Sec>

      <Sec n="⑤" title={t.secResult} reached={resultEvents.some(reached) || !resultEvents.length}
           current={current(...resultEvents)}>
        <ResultSection trades={p.trades} reflections={p.reflections} t={t} />
      </Sec>

      <RawRecord calls={p.modelCalls} from={turn.from} to={turn.to} t={t} />
    </div>
  )
}
