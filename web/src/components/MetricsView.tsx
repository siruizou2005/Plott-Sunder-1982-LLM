import { useMemo, useState } from 'react'
import { useStore } from '../store'
import { infoLabel, useT } from '../i18n'
import { EChart, axisStyle, tooltipStyle } from './EChart'
import { Empty, Panel, Tag, fmt, pct } from './ui'
import { STATE_TINT } from '../types'

/** The paper's own measures plus the two groups only an LLM market makes available. */
export function MetricsView() {
  const t = useT()
  const metrics = useStore((s) => s.metrics)
  const sessionIds = metrics ? Object.keys(metrics.sessions ?? {}) : []
  const [sid, setSid] = useState<string | null>(null)
  const s = metrics?.sessions?.[sid ?? sessionIds[0]]

  if (!metrics || !s) return <Empty>{t.noMetrics}</Empty>

  return (
    <div className="space-y-3">
      {sessionIds.length > 1 && (
        <div className="flex items-center gap-2">
          {sessionIds.map((k) => (
            <button key={k} onClick={() => setSid(k)}
                    className={`rounded px-2 py-1 text-xs ${
                      (sid ?? sessionIds[0]) === k
                        ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                        : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'}`}>
              session {k}
            </button>
          ))}
        </div>
      )}

      <Summary s={s} />
      <PriceVsTheory s={s} />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <EfficiencyChart s={s} />
        <PosteriorChart s={s} />
        <BasisDrift s={s} />
        <Table8 s={s} />
        <SpreadChart s={s} />
        <Violations s={s} />
      </div>
      <PeriodTable s={s} />
    </div>
  )
}

function Summary({ s }: { s: any }) {
  const t = useT()
  const tot = s.paper.totals ?? {}
  const pc = s.paper.price_changes_toward_re ?? {}
  const stat = (label: string, value: string, sub?: string) => (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700
                    dark:bg-slate-900">
      <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="tabular-nums text-lg font-semibold text-slate-800 dark:text-slate-100">{value}</div>
      {sub && <div className="text-[10px] text-slate-400">{sub}</div>}
    </div>
  )
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
      {stat(t.towardRe,
        pc.separating?.n ? `${(pc.separating.share_toward_re * 100).toFixed(0)}%` : '—',
        pc.separating?.n ? `${pc.separating.toward_re}/${pc.separating.n} · ${t.separating}` : undefined)}
      {stat(t.insiderRatio, pct(tot.insider_advantage_pct, 0))}
      {stat(t.calls, fmt(tot.calls))}
      {stat(t.cost, tot.cost_usd != null ? `$${tot.cost_usd}` : '—',
        tot.usage ? `${fmt((tot.usage.prompt_tokens ?? 0) + (tot.usage.completion_tokens ?? 0))} ${t.tokens}` : undefined)}
      {stat(t.wallClock, tot.wall_clock_s != null ? `${Math.round(tot.wall_clock_s / 60)} min` : '—')}
    </div>
  )
}

function PriceVsTheory({ s }: { s: any }) {
  const t = useT()
  const rows = s.paper.prices ?? []
  const option = useMemo(() => ({
    animation: false,
    grid: { left: 48, right: 14, top: 28, bottom: 30 },
    tooltip: { ...tooltipStyle },
    legend: { top: 0, textStyle: { fontSize: 10, color: '#64748b' },
              data: [t.meanPrice, t.lastPrice, t.rePrice, t.piPrice] },
    xAxis: { type: 'category', data: rows.map((r: any) => r.period),
             name: t.period, nameLocation: 'middle', nameGap: 20,
             nameTextStyle: { fontSize: 10, color: '#94a3b8' }, ...axisStyle },
    yAxis: { type: 'value', name: 'francs', nameTextStyle: { fontSize: 10, color: '#94a3b8' },
             ...axisStyle },
    series: [
      { name: t.rePrice, type: 'line', step: 'middle', data: rows.map((r: any) => r.re_price),
        lineStyle: { color: '#10b981', width: 2 }, symbol: 'none',
        markArea: { silent: true, data: rows.map((r: any, i: number) => ([
          { xAxis: i - 0.5, itemStyle: { color: STATE_TINT[r.state] } }, { xAxis: i + 0.5 }]))} },
      { name: t.piPrice, type: 'line', step: 'middle', data: rows.map((r: any) => r.pi_price),
        lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' }, symbol: 'none' },
      { name: t.meanPrice, type: 'line', data: rows.map((r: any) => r.mean_price),
        lineStyle: { color: '#0f172a', width: 2 }, itemStyle: { color: '#0f172a' },
        symbolSize: 6, connectNulls: true },
      { name: t.lastPrice, type: 'line', data: rows.map((r: any) => r.last_price),
        lineStyle: { color: '#4f7cff', width: 1, type: 'dotted' },
        itemStyle: { color: '#4f7cff' }, symbolSize: 4, connectNulls: true },
    ],
  }), [rows, t])
  return (
    <Panel title={`${t.meanPrice} — ${t.rePrice} / ${t.piPrice}`}>
      <EChart option={option} height={280} />
    </Panel>
  )
}

function EfficiencyChart({ s }: { s: any }) {
  const t = useT()
  const keys = Object.keys(s.paper.efficiency ?? {}).sort((a, b) => +a - +b)
  const option = useMemo(() => ({
    animation: false,
    grid: { left: 44, right: 14, top: 28, bottom: 26 },
    tooltip: { ...tooltipStyle },
    legend: { top: 0, textStyle: { fontSize: 10, color: '#64748b' },
              data: [t.efficiency, t.tradingEfficiency] },
    xAxis: { type: 'category', data: keys, ...axisStyle },
    yAxis: { type: 'value', name: '%', ...axisStyle },
    series: [
      { name: t.efficiency, type: 'bar', barMaxWidth: 14, itemStyle: { color: '#4f7cff' },
        data: keys.map((k) => s.paper.efficiency[k]?.E_pct ?? null) },
      { name: t.tradingEfficiency, type: 'line', symbolSize: 5,
        lineStyle: { color: '#e0803c', width: 2 }, itemStyle: { color: '#e0803c' },
        data: keys.map((k) => s.paper.efficiency[k]?.TE_pct ?? null),
        markLine: { silent: true, symbol: 'none', data: [{ yAxis: 100 }],
                    lineStyle: { color: '#10b981', type: 'dashed' } } },
    ],
  }), [s, t])
  return <Panel title={`${t.efficiency} / ${t.tradingEfficiency}`}><EChart option={option} /></Panel>
}

function PosteriorChart({ s }: { s: any }) {
  const t = useT()
  const rows = s.llm?.posterior_convergence ?? []
  const option = useMemo(() => ({
    animation: false,
    grid: { left: 44, right: 14, top: 28, bottom: 26 },
    tooltip: { ...tooltipStyle },
    legend: { top: 0, textStyle: { fontSize: 10, color: '#64748b' },
              data: [t.insiderMean, t.uninformedMean] },
    xAxis: { type: 'category', data: rows.map((r: any) => r.period), ...axisStyle },
    yAxis: { type: 'value', min: 0, max: 1, ...axisStyle },
    series: [
      { name: t.insiderMean, type: 'line', symbolSize: 5, connectNulls: true,
        data: rows.map((r: any) => r.insider_mean),
        lineStyle: { color: '#4f7cff', width: 2 }, itemStyle: { color: '#4f7cff' } },
      { name: t.uninformedMean, type: 'line', symbolSize: 5, connectNulls: true,
        data: rows.map((r: any) => r.uninformed_mean),
        lineStyle: { color: '#e0803c', width: 2 }, itemStyle: { color: '#e0803c' },
        markLine: { silent: true, symbol: 'none', data: [{ yAxis: 1 }],
                    lineStyle: { color: '#10b981', type: 'dashed' } } },
    ],
  }), [rows, t])
  return <Panel title={t.posteriorConv}><EChart option={option} /></Panel>
}

const BASIS_COLORS: Record<string, string> = {
  prior: '#94a3b8', clue: '#4f7cff', price: '#10b981',
  others_behavior: '#8b5cf6', spread: '#e0803c',
}

function BasisDrift({ s }: { s: any }) {
  const t = useT()
  const rows = s.llm?.basis_drift ?? []
  const keys = ['prior', 'clue', 'price', 'others_behavior', 'spread']
  const option = useMemo(() => ({
    animation: false,
    grid: { left: 44, right: 14, top: 28, bottom: 26 },
    tooltip: { ...tooltipStyle },
    legend: { top: 0, textStyle: { fontSize: 9, color: '#64748b' }, data: keys },
    xAxis: { type: 'category', data: rows.map((r: any) => r.period), ...axisStyle },
    yAxis: { type: 'value', max: 1, ...axisStyle },
    series: keys.map((k) => ({
      name: k, type: 'bar', stack: 'b', barMaxWidth: 20,
      itemStyle: { color: BASIS_COLORS[k] },
      data: rows.map((r: any) => r.shares?.[k] ?? 0),
    })),
  }), [rows, t])
  return <Panel title={t.basisDrift}><EChart option={option} /></Panel>
}

function Table8({ s }: { s: any }) {
  const t = useT()
  const t8 = s.paper.table8 ?? {}
  const keys = Object.keys(t8).sort((a, b) => +a - +b)
  const option = useMemo(() => ({
    animation: false,
    grid: { left: 44, right: 14, top: 28, bottom: 30 },
    tooltip: { ...tooltipStyle },
    legend: { top: 0, textStyle: { fontSize: 10, color: '#64748b' },
              data: [t.shareInsider, t.cumulativeShare] },
    xAxis: { type: 'category', data: keys, name: t.actionNumber, nameLocation: 'middle',
             nameGap: 20, nameTextStyle: { fontSize: 10, color: '#94a3b8' }, ...axisStyle },
    yAxis: { type: 'value', min: 0, max: 1, ...axisStyle },
    series: [
      { name: t.shareInsider, type: 'bar', barMaxWidth: 22, itemStyle: { color: '#8b5cf6' },
        data: keys.map((k) => t8[k]?.share_insider ?? null) },
      { name: t.cumulativeShare, type: 'line', symbolSize: 5,
        lineStyle: { color: '#0f172a', width: 2 }, itemStyle: { color: '#0f172a' },
        data: keys.map((k) => t8[k]?.cumulative_share_insider ?? null),
        markLine: { silent: true, symbol: 'none', data: [{ yAxis: 0.5 }],
                    lineStyle: { color: '#94a3b8', type: 'dashed' } } },
    ],
  }), [t8, t])
  return <Panel title={t.table8}><EChart option={option} /></Panel>
}

function SpreadChart({ s }: { s: any }) {
  const t = useT()
  const traj = s.book?.spread_trajectory ?? {}
  const keys = Object.keys(traj).sort((a, b) => +a - +b)
  const option = useMemo(() => ({
    animation: false,
    grid: { left: 44, right: 14, top: 28, bottom: 26 },
    tooltip: { ...tooltipStyle },
    legend: { top: 0, type: 'scroll', textStyle: { fontSize: 9, color: '#64748b' } },
    xAxis: { type: 'value', name: t.actionNumber, nameLocation: 'middle', nameGap: 20,
             nameTextStyle: { fontSize: 10, color: '#94a3b8' }, ...axisStyle },
    yAxis: { type: 'value', name: t.spread, ...axisStyle },
    series: keys.map((k, i) => ({
      name: `${t.period} ${k}`, type: 'line', symbol: 'none', smooth: true,
      lineStyle: { width: 1.5, opacity: 0.35 + 0.65 * (i / Math.max(1, keys.length - 1)) },
      data: (traj[k] ?? []).map((p: any) => [p.i, p.spread]),
    })),
  }), [traj, t])
  return <Panel title={t.spreadNarrowing}><EChart option={option} /></Panel>
}

function Violations({ s }: { s: any }) {
  const t = useT()
  const byReason = s.book?.violations?.by_reason ?? {}
  const keys = Object.keys(byReason)
  if (!keys.length) return <Panel title={t.violationsTitle}><Empty>—</Empty></Panel>
  const ap = s.book?.active_vs_passive ?? {}
  return (
    <Panel title={t.violationsTitle}>
      <div className="space-y-1">
        {keys.map((k) => (
          <div key={k} className="flex items-center justify-between text-xs">
            <span className="text-slate-500 dark:text-slate-400">{k}</span>
            <span className="tabular-nums font-medium">{byReason[k]}</span>
          </div>
        ))}
      </div>
      {Object.keys(ap).length > 0 && (
        <>
          <h3 className="mt-3 text-[10px] uppercase tracking-wide text-slate-400">{t.activePassive}</h3>
          {Object.entries<any>(ap).map(([who, v]) => (
            <div key={who} className="mt-1 flex items-center justify-between text-xs">
              <span className="text-slate-500">{who === 'insider' ? t.insiderMean : t.uninformedMean}</span>
              <span className="tabular-nums">
                {v.quote} / {v.accept_standing}
                <span className="ml-1 text-slate-400">
                  ({v.share_active != null ? `${(v.share_active * 100).toFixed(0)}%` : '—'})
                </span>
              </span>
            </div>
          ))}
        </>
      )}
    </Panel>
  )
}

function PeriodTable({ s }: { s: any }) {
  const t = useT()
  return (
    <Panel title={t.metricsTitle}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[46rem] text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wide text-slate-400">
              <th className="py-1">{t.period}</th>
              <th></th>
              <th className="text-right">{t.firstPrice}</th>
              <th className="text-right">{t.meanPrice}</th>
              <th className="text-right">{t.lastPrice}</th>
              <th className="text-right">{t.rePrice}</th>
              <th className="text-right">{t.piPrice}</th>
              <th className="text-right">{t.efficiency}</th>
              <th className="text-right">{t.tradingEfficiency}</th>
              <th className="text-right">{t.wrongHands}</th>
              <th className="text-right">{t.insiderRatio}</th>
            </tr>
          </thead>
          <tbody>
            {(s.paper.prices ?? []).map((r: any) => {
              const k = String(r.period)
              const eff = s.paper.efficiency?.[k] ?? {}
              const wh = s.paper.wrong_hands?.[k]?.RE ?? {}
              const ipr = s.paper.insider_profit_ratio?.[k] ?? {}
              return (
                <tr key={k} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-1 font-medium">{r.period}</td>
                  <td>
                    <Tag tone={r.state === 'X' ? 'blue' : 'amber'}>{r.state}</Tag>{' '}
                    <span className="text-[10px] text-slate-400">{infoLabel(t, r.info)}</span>
                    {r.separating && <span className="ml-1 text-[10px] text-emerald-600">◆</span>}
                  </td>
                  <td className="text-right tabular-nums text-slate-500">{fmt(r.first_price)}</td>
                  <td className="text-right tabular-nums font-semibold">{fmt(r.mean_price, 1)}</td>
                  <td className="text-right tabular-nums">{fmt(r.last_price)}</td>
                  <td className="text-right tabular-nums text-emerald-600">{r.re_price}</td>
                  <td className="text-right tabular-nums text-amber-600">{r.pi_price}</td>
                  <td className="text-right tabular-nums">{pct(eff.E_pct)}</td>
                  <td className="text-right tabular-nums">{pct(eff.TE_pct)}</td>
                  <td className="text-right tabular-nums">{wh.in_wrong_hands ?? '—'}</td>
                  <td className="text-right tabular-nums">{pct(ipr.ratio_pct, 0)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[10px] text-slate-400">◆ = {t.separating}</p>
    </Panel>
  )
}
