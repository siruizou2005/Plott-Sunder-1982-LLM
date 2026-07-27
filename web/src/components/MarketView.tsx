import { Fragment, useMemo } from 'react'
import { useStore, type DerivedState, theoryFor } from '../store'
import { useT, type Strings } from '../i18n'
import { Empty, Panel, Tag, fmt } from './ui'
import { EChart, axisStyle, tooltipStyle } from './EChart'
import { STATE_TINT, TYPE_COLOR, type RoundOutcome, type SeatState } from '../types'


/** The only cell where RE and PI disagree: six insiders and the Y state. Everywhere else
 *  the two models predict the same price, so those periods carry no identifying power. */
const separating = (info?: string, state?: string | null) =>
  info === 'insider' && state === 'Y'

const holderLabel = (t: Strings, spec: string) =>
  spec === 'I_insider' ? `I · ${t.insiderMean}`
    : spec === 'I_uninformed' ? `I · ${t.uninformedMean}`
      : spec

function holderSeats(spec: string, seats: SeatState[]): SeatState[] {
  if (spec === 'I_insider') return seats.filter((s) => s.type === 'I' && s.insider)
  if (spec === 'I_uninformed') return seats.filter((s) => s.type === 'I' && !s.insider)
  return seats.filter((s) => s.type === spec)
}

// ---------------------------------------------------------------- round strip

const OUTCOME_MARK: Record<RoundOutcome, string> = {
  traded: '✓', posted: '·', no_quote: '—', violation: '!',
}

/**
 * The round's speaking order, which the engine reshuffles every round and records in
 * `round_start.order`. Answers "how far through the round are we and who is next" at a
 * glance, and doubles as a jump target.
 */
function RoundStrip({ d }: { d: DerivedState }) {
  const t = useT()
  const { timeline, seek, cursor } = useStore()
  if (!d.order.length) return null

  const jumpTo = (seat: string) => {
    for (let i = 0; i < timeline.length; i++) {
      const x = timeline[i]
      if (x.kind === 'turn' && x.seat === seat && x.period === d.period && x.round === d.round) {
        return seek(i)
      }
    }
  }

  return (
    <Panel title={`${t.roundStrip} · ${t.round} ${d.round || '—'}`}
           right={<span className="text-[10px] text-slate-400">{t.clickToJump}</span>}>
      <div className="flex flex-wrap gap-1">
        {d.order.map((seat, i) => {
          const o = d.roundOutcomes[seat]
          const acting = d.turn?.kind === 'turn' && d.turn.seat === seat
          const next = d.nextSeat === seat
          const done = o !== undefined && !acting
          return (
            <button
              key={seat}
              onClick={() => jumpTo(seat)}
              title={`${i + 1}. ${seat}`}
              className={`flex min-w-[3.2rem] items-center justify-center gap-1 rounded px-1.5
                          py-1 text-[11px] font-medium tabular-nums transition
                          hover:ring-2 hover:ring-slate-400 ${
                acting ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                  : next ? 'bg-amber-100 text-amber-900 ring-1 ring-amber-400 dark:bg-amber-950 dark:text-amber-300'
                    : done ? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                      : 'bg-slate-50 text-slate-300 dark:bg-slate-900 dark:text-slate-600'}`}
            >
              <span className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{ background: TYPE_COLOR[d.seats[seat]?.type] ?? '#cbd5e1' }} />
              {seat}
              <span className={o === 'violation' ? 'text-rose-500' : 'opacity-60'}>
                {o ? OUTCOME_MARK[o] : ''}
              </span>
            </button>
          )
        })}
        <span className="ml-1 self-center text-[10px] text-slate-400">
          {d.nextSeat ? `${t.nextUp}: ${d.nextSeat}` : t.endOfRound}
        </span>
      </div>
    </Panel>
  )
}

// ---------------------------------------------------------------- book

function BookPanel({ d }: { d: DerivedState }) {
  const t = useT()
  const { bid, ask, spread } = d.book
  // How many market actions a quote has survived. A quote nobody will take for ten actions
  // says something quite different from one posted a moment ago.
  const age = (q: any) => (q?.posted_at != null ? Math.max(0, d.actionSeq - q.posted_at) : null)

  const side = (label: string, q: any, tone: 'green' | 'red', rule: string) => (
    <div className="flex-1">
      <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="flex items-baseline gap-1.5">
        <span className={`tabular-nums text-xl font-semibold ${
          tone === 'green' ? 'text-emerald-600 dark:text-emerald-400'
            : 'text-rose-600 dark:text-rose-400'}`}>
          {q ? fmt(q.price) : t.none}
        </span>
        {q && <span className="text-[11px] text-slate-400">{q.seat}</span>}
      </div>
      <div className="text-[10px] text-slate-400">
        {q ? <>{rule} {q.price} · {t.quoteAge} {age(q)}</> : ' '}
      </div>
    </div>
  )

  return (
    <Panel title={t.book}>
      <div className="flex items-start gap-3">
        {side(t.standingBid, bid, 'green', t.mustExceed)}
        <div className="shrink-0 px-2 text-center">
          <div className="text-[10px] uppercase tracking-wide text-slate-400">{t.spread}</div>
          <div className="tabular-nums text-xl font-semibold text-slate-700 dark:text-slate-200">
            {spread === null ? t.undefinedSpread : fmt(spread)}
          </div>
        </div>
        {side(t.standingAsk, ask, 'red', t.mustUndercut)}
      </div>
    </Panel>
  )
}

// ---------------------------------------------------------------- price chart

function PriceChart({ d }: { d: DerivedState }) {
  const theory = useStore((s) => s.theory)
  const t = useT()
  const events = useStore((s) => s.events)
  const periods = useStore((s) => s.periods)
  const seek = useStore((s) => s.seek)

  // The event walk depends only on the log, so it must not sit inside the per-cursor memo:
  // holding an arrow key steps many times a second and would re-scan every event each time.
  const buckets = useMemo(() => {
    // One bucket per period, each given EQUAL width on the x axis. Spacing by trade index
    // instead would make a busy period twelve times wider than a quiet one and squeeze the
    // quiet ones — including empty ones — out of existence, which is exactly what made the
    // period labels unreadable before.
    type Bucket = { period: number; info: string; state: string | null;
                    trades: { price: number; ev: number }[] }
    const out: Bucket[] = []
    events.forEach((e, i) => {
      if (e.type === 'period_start') {
        out.push({ period: e.payload.period, info: e.payload.info,
                   state: e.payload.state, trades: [] })
      } else if (e.type === 'trade' && out.length) {
        out[out.length - 1].trades.push({ price: e.payload.price, ev: i })
      }
    })
    return out
  }, [events])

  const option = useMemo(() => {
    const xOf = (bi: number, k: number, n: number) => bi + (n ? (k + 0.5) / n : 0.5)
    const pts = buckets.flatMap((b, bi) =>
      b.trades.map((tr, k) => ({
        x: xOf(bi, k, b.trades.length), price: tr.price,
        period: b.period, seen: tr.ev <= d.subEventIndex,
      })))

    const stepLine = (key: 'RE' | 'PI') => buckets.flatMap((b, bi) => {
      const v = theoryFor(theory, b.period, b.info, b.state)?.[key]
      return v === undefined ? [] : [[bi, v], [bi + 1, v], [null, null]]
    })

    // Anchoring y at 0 threw away 40% of the plot; frame the data plus the theory lines.
    const vals = [...pts.map((p) => p.price),
                  ...buckets.flatMap((b) => {
                    const th = theoryFor(theory, b.period, b.info, b.state)
                    return th ? [th.RE, th.PI] : []
                  })]
    const lo = vals.length ? Math.min(...vals) : 0
    const hi = vals.length ? Math.max(...vals) : 400
    const pad = Math.max(20, (hi - lo) * 0.12)
    const yMin = Math.floor((lo - pad) / 25) * 25
    const yMax = Math.ceil((hi + pad) / 25) * 25

    // Play head: the last trade already folded in, else the left edge of the current period.
    const seenPts = pts.filter((p) => p.seen)
    const headX = seenPts.length ? seenPts[seenPts.length - 1].x
      : Math.max(0, buckets.findIndex((b) => b.period === d.period))

    const areas = buckets.map((b, bi) => [
      { xAxis: bi, itemStyle: { color: STATE_TINT[b.state ?? ''] ?? 'transparent' } },
      { xAxis: bi + 1 },
    ])

    // The CLOSING trade of each period, drawn big and filled.
    //
    // Every trade used to be an identical small circle, which buried the one number that
    // actually discriminates: a separating period opens near the PI price and drifts to
    // the RE price, so the closing trade says which model the market landed on while the
    // scatter of all trades merely fills the band between them.
    const closes = buckets.flatMap((b, bi) => {
      if (!b.trades.length) return []
      const last = b.trades[b.trades.length - 1]
      const sep = separating(b.info, b.state)
      return [{
        value: [xOf(bi, b.trades.length - 1, b.trades.length), last.price, b.period],
        symbolSize: sep ? 11 : 8,
        itemStyle: {
          color: last.ev <= d.subEventIndex ? (sep ? '#7c3aed' : '#0f172a')
            : 'rgba(15,23,42,0.15)',
          borderColor: '#fff', borderWidth: 1.5,
        },
      }]
    })

    return {
      animation: false,
      grid: { left: 46, right: 12, top: 24, bottom: 8 },
      tooltip: {
        ...tooltipStyle, trigger: 'item',
        formatter: (p: any) => `${t.period} ${p.data.value[2]} · ${t.tradePrice} ${p.data.value[1]}`,
      },
      legend: {
        top: 0, right: 0, itemWidth: 14, itemHeight: 8,
        textStyle: { fontSize: 10, color: '#64748b' },
        data: [t.rePrice, t.piPrice, t.tradePrice, t.closePrice],
      },
      xAxis: { type: 'value', min: 0, max: Math.max(1, buckets.length), show: false },
      yAxis: { type: 'value', min: yMin, max: yMax, name: 'francs',
               nameTextStyle: { fontSize: 10, color: '#94a3b8' }, ...axisStyle },
      series: [
        { name: t.rePrice, type: 'line', data: stepLine('RE'), showSymbol: false,
          lineStyle: { color: '#10b981', width: 1.5 }, z: 2,
          markArea: { silent: true, data: areas },
          markLine: {
            silent: true, symbol: 'none',
            data: [{ xAxis: headX }],
            lineStyle: { color: '#0f172a', width: 1.5, type: 'solid', opacity: 0.55 },
            label: { show: false },
          } },
        { name: t.piPrice, type: 'line', data: stepLine('PI'), showSymbol: false,
          lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed' }, z: 2 },
        { name: t.tradePrice, type: 'line', z: 3, showSymbol: true, symbolSize: 5,
          data: pts.map((p) => ({
            value: [p.x, p.price, p.period],
            itemStyle: { color: p.seen ? '#0f172a' : 'rgba(15,23,42,0.13)' },
          })),
          lineStyle: { color: 'rgba(15,23,42,0.3)', width: 1 } },
        { name: t.closePrice, type: 'scatter', z: 4, data: closes,
          symbol: 'circle',
          tooltip: { formatter: (p: any) =>
            `${t.period} ${p.data.value[2]} · ${t.closePrice} ${p.data.value[1]}` } },
      ],
    }
  }, [buckets, d.subEventIndex, d.period, t])

  const swatch = (state: string, label: string) => (
    <span className="inline-flex items-center gap-1 text-[10px] text-slate-400">
      <span className="inline-block h-2.5 w-4 rounded-sm border border-slate-200
                       dark:border-slate-700"
            style={{ background: STATE_TINT[state] }} />
      {label}
    </span>
  )

  return (
    <Panel title={t.priceChart}
           right={<span className="flex gap-2">{swatch('X', t.stateX)}{swatch('Y', t.stateY)}</span>}>
      {buckets.length ? (
        <>
          <EChart option={option} height={200} />
          {/* The period ruler. Labels used to sit inside the plot, where a price cloud at 400
              buried them; down here they are always legible and double as jump targets. */}
          <div className="mt-1 flex" style={{ paddingLeft: 46, paddingRight: 12 }}>
            {buckets.map((b, bi) => (
              <button
                key={bi}
                onClick={() => {
                  const m = periods.find((p) => p.period === b.period)
                  if (m) seek(m.step)
                }}
                title={t.clickToJump}
                className={`min-w-0 flex-1 border-r border-slate-200 py-0.5 text-center
                            text-[10px] leading-tight last:border-r-0 hover:bg-slate-100
                            dark:border-slate-700 dark:hover:bg-slate-800 ${
                  b.period === d.period
                    ? 'font-semibold text-slate-800 dark:text-slate-100'
                    : 'text-slate-400'}`}
              >
                <div className="tabular-nums">{b.period}</div>
                <div className="truncate">
                  {b.state}
                  {/* Only these periods can tell the two models apart. */}
                  {separating(b.info, b.state) &&
                    <span className="ml-0.5 text-violet-600 dark:text-violet-400">◆</span>}
                </div>
              </button>
            ))}
          </div>
        </>
      ) : <Empty>{t.noTrades}</Empty>}
    </Panel>
  )
}

// ---------------------------------------------------------------- investors

function TheoryCheck({ d, t }: { d: DerivedState; t: Strings }) {
  const theory = useStore((s) => s.theory)
  const seats = Object.values(d.seats)
  const spec = theory[`${d.info}|${d.state}`]?.holder
  if (!spec || !seats.length) return null
  const total = seats.reduce((n, s) => n + s.certs, 0)
  if (!total) return null
  // Before the first trade of a period, holdings are the freshly reset endowment: every
  // seat holds two, so type I mechanically holds 8 of 24 and this would report "33%, does
  // not match RE" in every single period regardless of what the market did. The comparison
  // only means something once trading has moved something.
  if (!d.marketLog.some((e) => e.outcome === 'traded' || e.outcome === 'crossed_auto')) {
    return null
  }

  const share = (which: 'RE' | 'PI') => {
    const held = holderSeats(spec[which], seats).reduce((n, s) => n + s.certs, 0)
    return { held, pct: Math.round((held / total) * 100) }
  }
  const re = share('RE')
  const ok = re.pct >= 75

  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-slate-100
                    pt-2 text-[11px] text-slate-500 dark:border-slate-800 dark:text-slate-400">
      <Tag tone="violet">{t.theoryCheck}</Tag>
      <span>{t.reHolder} <b className="text-slate-700 dark:text-slate-200">
        {holderLabel(t, spec.RE)}</b></span>
      <span className="text-slate-300">·</span>
      <span>{t.piHolder} <b className="text-slate-700 dark:text-slate-200">
        {holderLabel(t, spec.PI)}</b></span>
      <span className="text-slate-300">·</span>
      <span>
        {t.actualHolder} <span className="tabular-nums">{re.held}/{total}</span>
        {' '}<span className={ok ? 'text-emerald-600' : 'text-amber-600'}>
          ({re.pct}% — {ok ? t.holdersMatch : t.holdersDiffer})
        </span>
      </span>
    </div>
  )
}

function AgentGrid({ d }: { d: DerivedState }) {
  const t = useT()
  const seats = Object.values(d.seats).sort((a, b) => a.seat.localeCompare(b.seat))
  if (!seats.length) return <Panel title={t.agents}><Empty>{t.waiting}</Empty></Panel>

  return (
    <Panel title={t.agents}
           right={<span className="text-[10px] text-slate-400">{t.hiddenNote}</span>}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wide text-slate-400">
              <th className="py-1">{t.seat}</th>
              <th>{t.type}</th>
              <th>{t.card}</th>
              <th className="text-right">{t.certs}</th>
              <th className="text-right">{t.cash}</th>
              <th className="text-right">{t.lastProfit}</th>
              <th className="text-right">{t.cumulative}</th>
            </tr>
          </thead>
          <tbody>
            {seats.map((s) => {
              const acting = d.turn?.kind === 'turn' && d.turn.seat === s.seat
              return (
                <tr key={s.seat}
                    className={`border-t border-slate-100 dark:border-slate-800 ${
                      acting ? 'bg-slate-900/5 dark:bg-slate-100/5'
                        : d.nextSeat === s.seat ? 'bg-amber-50 dark:bg-amber-950/25' : ''}`}>
                  <td className="py-0.5 font-medium text-slate-700 dark:text-slate-200">
                    {acting && <span className="mr-0.5 text-slate-900 dark:text-slate-100">▸</span>}
                    {s.seat}
                    {acting && <span className="ml-1 text-[10px] text-slate-400">{t.nowActing}</span>}
                    {d.nextSeat === s.seat &&
                      <span className="ml-1 text-[10px] text-amber-600">{t.nextUp}</span>}
                  </td>
                  <td>
                    <span className="inline-block h-2 w-2 rounded-full align-middle"
                          style={{ background: TYPE_COLOR[s.type] ?? '#94a3b8' }} />
                    <span className="ml-1 text-slate-500 dark:text-slate-400">{s.type || '—'}</span>
                    {/* The permanent insider roster. Subjects were never told how many
                        insiders there were, who they were, or that they never changed. */}
                    {s.insider && (
                      <span className="ml-1 rounded bg-violet-100 px-1 text-[9px] font-medium
                                       text-violet-700 dark:bg-violet-950 dark:text-violet-300"
                            title={t.audienceOnly}>◆</span>
                    )}
                  </td>
                  <td>
                    {s.card
                      ? <Tag tone={s.card === 'X' ? 'blue' : 'amber'}>{s.card} · {t.insiderBadge}</Tag>
                      : <span className="text-slate-300 dark:text-slate-600">{t.blank}</span>}
                  </td>
                  <td className="text-right tabular-nums">{s.certs}</td>
                  <td className="text-right tabular-nums text-slate-500">{fmt(s.cash)}</td>
                  <td className={`text-right tabular-nums ${
                    (s.lastProfit ?? 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                    {s.lastProfit === null ? '—' : fmt(s.lastProfit)}
                  </td>
                  <td className="text-right tabular-nums font-medium">{fmt(s.cumulative)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <TheoryCheck d={d} t={t} />
    </Panel>
  )
}

// ---------------------------------------------------------------- market log

function MarketLog({ d }: { d: DerivedState }) {
  const t = useT()
  if (!d.marketLog.length) {
    return <Panel title={`${t.period} ${d.period} — ${t.tabMarket}`}><Empty>{t.noTrades}</Empty></Panel>
  }
  // Name buyer and seller rather than the quote's side: whoever accepts a standing BID is
  // the SELLER, so a bare "bid" tag next to their seat reads exactly backwards.
  const outcomeText = (e: any) => {
    if (e.outcome === 'posted') return t.posted
    if (e.outcome === 'superseded') return t.superseded
    const who = e.buyer && e.seller ? `${e.seller} → ${e.buyer}` : (e.counterparty ?? '')
    return `${e.outcome === 'crossed_auto' ? t.crossedAuto : t.traded} · ${who}`
  }
  // Which log lines this turn produced, so the entry you are looking at is findable.
  const mine = new Set(d.turnEvents.filter((e) => e.type === 'action')
                                   .map((e) => e.payload?.seq).filter((s) => s !== undefined))

  const rows = d.marketLog.slice().reverse()
  return (
    <Panel title={`${t.period} ${d.period} — ${t.tabMarket}`}>
      <div className="max-h-72 overflow-y-auto">
        <table className="w-full text-xs">
          <tbody>
            {rows.map((e, i) => (
              <Fragment key={e.seq}>
                {/* Rounds are the engine's unit of turn-taking; without a divider a
                    three-round period reads as one undifferentiated list. */}
                {(i === 0 || rows[i - 1].round !== e.round) && (
                  <tr>
                    <td colSpan={5} className="pt-1.5 text-[10px] uppercase tracking-wide
                                               text-slate-400">
                      {t.round} {e.round}
                    </td>
                  </tr>
                )}
                <tr className={`border-t border-slate-100 dark:border-slate-800 ${
                      mine.has(e.seq) ? 'bg-amber-50 dark:bg-amber-950/30' : ''}`}>
                  <td className="w-8 py-1 tabular-nums text-slate-400">#{e.seq}</td>
                  <td className="w-14 font-medium text-slate-700 dark:text-slate-200">{e.seat}</td>
                  <td className="w-16">
                    <Tag tone={e.side === 'bid' ? 'green' : 'red'}>
                      {e.action === 'accept_standing' ? '↩ ' : ''}
                      {e.side === 'bid' ? t.bid : t.ask}
                    </Tag>
                  </td>
                  <td className="w-16 text-right tabular-nums font-semibold">{fmt(e.price)}</td>
                  <td className="pl-3 text-slate-500 dark:text-slate-400">{outcomeText(e)}</td>
                </tr>
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[10px] text-slate-400">↩ = {t.acceptStanding}</p>
    </Panel>
  )
}

export function MarketView({ d }: { d: DerivedState }) {
  return (
    <div className="space-y-3">
      <RoundStrip d={d} />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          <PriceChart d={d} />
          <AgentGrid d={d} />
        </div>
        <div className="space-y-3">
          <BookPanel d={d} />
          <MarketLog d={d} />
        </div>
      </div>
    </div>
  )
}
