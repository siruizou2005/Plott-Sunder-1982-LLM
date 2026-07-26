import { useMemo } from 'react'
import { useStore } from '../store'
import { useT } from '../i18n'
import { EChart, axisStyle, tooltipStyle } from './EChart'
import { Empty, Panel, fmt } from './ui'

/**
 * Latent supply and demand, recovered from broadcast votes.
 *
 * Every broadcast records how many investors WOULD have taken the quote — not only the one
 * who won the random tie-break. In an oral auction the losers never speak, so nobody can
 * record them; here they are in the log.
 *
 * The two sides are kept apart because they measure opposite things:
 *   an ASK accepted by k agents  ->  k agents would BUY at that price   (demand)
 *   a BID accepted by k agents   ->  k agents would SELL at that price  (supply)
 * Pooling them would add willing buyers to willing sellers and call the sum "demand".
 *
 * Built from the raw events rather than metrics.json so it also works mid-run.
 */
export function DemandView() {
  const t = useT()
  const events = useStore((s) => s.events)

  const rows = useMemo(() => {
    const m = new Map<number, any>()
    for (const e of events) {
      if (e.type !== 'broadcast') continue
      const price = e.payload.quote.price
      const kind = e.payload.quote.side === 'ask' ? 'demand' : 'supply'
      const r = m.get(price) ?? {
        price, demandQuotes: 0, demandWilling: 0, demandAsked: 0,
        supplyQuotes: 0, supplyWilling: 0, supplyAsked: 0,
      }
      const k = kind === 'demand' ? 'demand' : 'supply'
      r[`${k}Quotes`]++
      r[`${k}Willing`] += e.payload.n_accept ?? 0
      r[`${k}Asked`] += e.payload.recipients?.length ?? 0
      m.set(price, r)
    }
    return [...m.values()].sort((a, b) => a.price - b.price)
  }, [events])

  const option = useMemo(() => ({
    animation: false,
    grid: { left: 48, right: 20, top: 30, bottom: 36 },
    tooltip: { ...tooltipStyle, trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10, color: '#64748b' },
              data: [t.willingBuyers, t.willingSellers] },
    xAxis: {
      type: 'category', name: t.price, nameLocation: 'middle', nameGap: 24,
      nameTextStyle: { fontSize: 10, color: '#94a3b8' },
      data: rows.map((r) => r.price), ...axisStyle,
    },
    yAxis: { type: 'value', name: t.willingCount,
             nameTextStyle: { fontSize: 10, color: '#94a3b8' }, ...axisStyle },
    series: [
      { name: t.willingBuyers, type: 'bar', data: rows.map((r) => r.demandWilling || null),
        itemStyle: { color: '#4f7cff' }, barMaxWidth: 16 },
      { name: t.willingSellers, type: 'bar', data: rows.map((r) => r.supplyWilling || null),
        itemStyle: { color: '#e0803c' }, barMaxWidth: 16 },
    ],
  }), [rows, t])

  if (!rows.length) return <Empty>{t.waiting}</Empty>

  return (
    <div className="space-y-3">
      <Panel title={t.demandTitle}>
        <p className="mb-3 max-w-3xl text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
          {t.demandBlurb}
        </p>
        <EChart option={option} height={300} />
      </Panel>

      <Panel title={t.demandTitle}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wide text-slate-400">
                <th className="py-1">{t.price}</th>
                <th className="text-right">{t.willingBuyers}</th>
                <th className="text-right">{t.acceptRate}</th>
                <th className="text-right">{t.willingSellers}</th>
                <th className="text-right">{t.acceptRate}</th>
                <th className="text-right">{t.quotesAt}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.price} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-1 tabular-nums font-medium">{fmt(r.price)}</td>
                  <td className="text-right tabular-nums text-blue-600 dark:text-blue-400">
                    {r.demandQuotes ? r.demandWilling : '—'}
                  </td>
                  <td className="text-right tabular-nums text-slate-400">
                    {r.demandAsked ? `${(100 * r.demandWilling / r.demandAsked).toFixed(0)}%` : '—'}
                  </td>
                  <td className="text-right tabular-nums text-amber-600 dark:text-amber-400">
                    {r.supplyQuotes ? r.supplyWilling : '—'}
                  </td>
                  <td className="text-right tabular-nums text-slate-400">
                    {r.supplyAsked ? `${(100 * r.supplyWilling / r.supplyAsked).toFixed(0)}%` : '—'}
                  </td>
                  <td className="text-right tabular-nums text-slate-400">
                    {r.demandQuotes + r.supplyQuotes}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}
