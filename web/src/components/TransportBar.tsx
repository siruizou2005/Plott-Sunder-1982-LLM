import { useStore } from '../store'
import { useT } from '../i18n'
import { Btn } from './ui'
import { STATE_TINT_SOLID } from '../types'
import type { DerivedState } from '../store'

export function TransportBar({ d }: { d: DerivedState }) {
  const t = useT()
  const { playing, play, pause, stepTurn, stepSub, seek, speed, setSpeed, timeline, periods,
          cursor, sub, tab, setTab, meta } = useStore()
  const total = Math.max(1, timeline.length)
  const nSubs = Math.max(1, d.turn?.subs.length ?? 1)
  const states: string[] = meta?.sequence?.states ?? []

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-slate-200
                    bg-slate-50 px-4 py-2 dark:border-slate-700 dark:bg-slate-950">
      <div className="flex items-center gap-1" title={t.keysHint}>
        <Btn onClick={() => stepTurn(-1)} disabled={cursor <= 0} title={t.stepTurnBack}>⏮</Btn>
        <Btn onClick={() => stepSub(-1)} title={t.stepBack}>◀</Btn>
        <Btn onClick={() => (playing ? pause() : play())} active={playing}>
          {playing ? `⏸ ${t.pause}` : `▶ ${t.play}`}
        </Btn>
        <Btn onClick={() => stepSub(1)} title={t.stepFwd}>▶</Btn>
        <Btn onClick={() => stepTurn(1)} disabled={cursor >= total - 1} title={t.stepTurnFwd}>⏭</Btn>
      </div>

      <label className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400">
        {t.speed}
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}
                className="rounded border border-slate-300 bg-white px-1 py-0.5 text-[11px]
                           dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
          {[0.5, 1, 2, 4, 8].map((s) => <option key={s} value={s}>{s}×</option>)}
        </select>
      </label>

      {/* The slider walks TURNS. Dragging it lands on each turn completed, which is what you
          want when scanning; the arrow keys go finer. */}
      <input
        type="range" min={0} max={total - 1} value={Math.min(cursor, total - 1)}
        onChange={(e) => seek(Number(e.target.value))}
        className="h-1 min-w-[8rem] flex-1 cursor-pointer accent-slate-900 dark:accent-slate-200"
      />
      <span className="tabular-nums text-[11px] text-slate-500 dark:text-slate-400">
        {t.turnLabel} {cursor + 1} {t.of} {total}
        {nSubs > 1 && <span className="ml-1.5 text-slate-400">
          {t.substep} {sub + 1}/{nSubs}
        </span>}
      </span>

      {/* Twelve chips beat dragging a 500-position slider blind. Tinted by the realized
          dividend, which is audience-only information — hence the muted palette. */}
      {periods.length > 1 && (
        <div className="flex items-center gap-1" title={t.jumpPeriod}>
          <span className="text-[10px] uppercase tracking-wide text-slate-400">{t.period}</span>
          {periods.map((p) => (
            <button
              key={p.period}
              onClick={() => seek(p.step)}
              title={`${t.jumpPeriod} ${p.period}`}
              className={`h-5 w-5 rounded text-[10px] font-medium tabular-nums transition
                          hover:ring-2 hover:ring-slate-400 ${
                d.period === p.period
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                  : 'text-slate-600 dark:text-slate-300'}`}
              style={d.period === p.period ? undefined
                : { background: STATE_TINT_SOLID[states[p.period - 1]] ?? '#e2e8f0' }}
            >
              {p.period}
            </button>
          ))}
        </div>
      )}

      <nav className="ml-auto flex gap-1">
        {[['market', t.tabMarket], ['agent', t.tabAgent], ['demand', t.tabDemand],
          ['metrics', t.tabMetrics]].map(([k, label]) => (
          <Btn key={k} onClick={() => setTab(k)} active={tab === k}>{label}</Btn>
        ))}
      </nav>
    </div>
  )
}
