import { useEffect } from 'react'

import { useStore } from '../store'
import { useT } from '../i18n'
import { Tag } from './ui'

/**
 * The market a run belongs to, and whether it is one of Plott & Sunder's.
 *
 * Logs written before the engine recorded `market` are market 3 — the only market that
 * existed then — which is the same reading metrics.py applies to them, and a fact about
 * when they were written rather than a guess. Null until the run's meta arrives, so the
 * header can say "Plott & Sunder 1982" instead of claiming a market it does not yet know.
 *
 * `paper` comes from the run's own meta (`ps1982 backfill-meta` fills it in for older
 * runs). Market 6 is the equidistant control of Table 7 and is OURS, so titling it
 * "Plott & Sunder 1982 — Market 6" would credit them with a market they never ran. Meta
 * that predates the field is from before market 6 existed, hence the `!== false`.
 */
function marketOf(meta: any): { n: number; paper: boolean } | null {
  if (!meta) return null
  const n = typeof meta?.market?.number === 'number' ? meta.market.number
    : typeof meta?.config?.market === 'number' ? meta.config.market : 3
  return { n, paper: meta?.market?.paper !== false }
}

export function Header() {
  const t = useT()
  const { lang, setLang, connected, runs, runId, load, live, meta } = useStore()

  const market = marketOf(meta)
  const title = market == null ? t.titleBare
    : (market.paper ? t.title : t.titleControl).replace('{n}', String(market.n))
  // The tab is how you tell two open viewers apart, so it carries the market too.
  useEffect(() => { document.title = title }, [title])

  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-slate-200
                       bg-white px-4 py-2.5 dark:border-slate-700 dark:bg-slate-900">
      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
          {title}
        </h1>
        <p className="truncate text-[11px] text-slate-500 dark:text-slate-400">{t.subtitle}</p>
      </div>

      <div className="ml-auto flex items-center gap-2">
        {meta?.sequence?.name && (
          <Tag tone="violet" title={meta.sequence.note}>
            {t.sequenceLabel}: {meta.sequence.name}
          </Tag>
        )}
        {live && <Tag tone="red">{t.live}</Tag>}

        <select
          value={runId ?? ''}
          onChange={(e) => load(e.target.value)}
          className="max-w-[22rem] rounded border border-slate-300 bg-white px-2 py-1 text-xs
                     text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
        >
          <option value="" disabled>{runs.length ? t.pickRun : t.noRuns}</option>
          {/* Grouped by the runs/ subdirectory, so the six sessions that ARE the result
              do not sit in one flat list with the shakedowns and the scripted baselines. */}
          {Object.entries(
            runs.reduce<Record<string, typeof runs>>((acc, r) => {
              (acc[r.group ?? ''] ??= []).push(r)
              return acc
            }, {}),
          ).map(([group, rs]) => (
            group
              ? <optgroup key={group} label={group}>
                  {rs.map((r) => (
                    <option key={r.runId} value={r.runId}>
                      {r.name} · {r.stamp}
                      {r.agentKinds.length ? ` · ${r.agentKinds.join('/')}` : ''}
                    </option>
                  ))}
                </optgroup>
              : rs.map((r) => (
                  <option key={r.runId} value={r.runId}>
                    {r.name} · {r.stamp}
                    {r.agentKinds.length ? ` · ${r.agentKinds.join('/')}` : ''}
                  </option>
                ))
          ))}
        </select>

        <span className={`inline-block h-2 w-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-slate-400'}`}
              title={connected ? t.connected : t.offline} />

        <div className="flex overflow-hidden rounded border border-slate-300 dark:border-slate-600">
          {(['en', 'zh'] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`px-2 py-1 text-[11px] font-medium transition ${
                lang === l
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                  : 'bg-white text-slate-600 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-300'
              }`}
            >
              {l === 'en' ? 'EN' : '中'}
            </button>
          ))}
        </div>
      </div>
    </header>
  )
}
