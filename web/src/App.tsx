import { useEffect, useMemo } from 'react'
import { derive, useStore } from './store'
import { useT } from './i18n'
import { Header } from './components/Header'
import { TransportBar } from './components/TransportBar'
import { TurnHeader } from './components/TurnHeader'
import { MarketView } from './components/MarketView'
import { AgentTrail } from './components/AgentTrail'
import { DemandView } from './components/DemandView'
import { MetricsView } from './components/MetricsView'
import { Empty } from './components/ui'

export default function App() {
  const t = useT()
  const { connect, events, timeline, cursor, sub, seatTypes, tab, error, runs, stepTurn,
          stepSub, playing, play, pause } = useStore()

  useEffect(() => { connect() }, [])

  // Keyboard transport. The plain arrows walk sub-steps and roll over turn boundaries, so
  // holding one key traverses the whole session in reading order; shift jumps whole turns.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (el?.tagName === 'INPUT' || el?.tagName === 'SELECT' || el?.tagName === 'TEXTAREA') return
      if (e.code === 'Space') { e.preventDefault(); playing ? pause() : play() }
      else if (e.code === 'ArrowRight') e.shiftKey ? stepTurn(1) : stepSub(1)
      else if (e.code === 'ArrowLeft') e.shiftKey ? stepTurn(-1) : stepSub(-1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [playing, play, pause, stepTurn, stepSub])

  const d = useMemo(() => derive(events, timeline, cursor, sub, seatTypes),
                    [events, timeline, cursor, sub, seatTypes])

  const ready = runs.length && events.length && timeline.length

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <Header />
      <TransportBar d={d} />
      {/* Shared by the market and trail tabs: switching between them must not lose the
          thread of which turn you were following. */}
      {!!ready && (tab === 'market' || tab === 'agent') && <TurnHeader d={d} />}
      {error && (
        <p className="border-b border-rose-200 bg-rose-50 px-4 py-1.5 text-xs text-rose-700
                      dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">{error}</p>
      )}
      <main className="p-3">
        {!runs.length ? <Empty>{t.noRuns}</Empty>
          : !ready ? <Empty>{t.loading}</Empty>
          : tab === 'market' ? <MarketView d={d} />
          : tab === 'agent' ? <AgentTrail d={d} />
          : tab === 'demand' ? <DemandView />
          : <MetricsView />}
      </main>
    </div>
  )
}
