import React from 'react'

export function Panel({ title, right, children, className = '' }: {
  title?: React.ReactNode
  right?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white shadow-sm
                         dark:border-slate-700 dark:bg-slate-900 ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-200
                           px-3 py-2 dark:border-slate-700">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500
                         dark:text-slate-400">{title}</h2>
          {right}
        </header>
      )}
      <div className="p-3">{children}</div>
    </section>
  )
}

export function Tag({ children, tone = 'slate', title }: {
  children: React.ReactNode
  tone?: 'slate' | 'blue' | 'amber' | 'green' | 'red' | 'violet'
  title?: string
}) {
  const tones: Record<string, string> = {
    slate: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
    blue: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300',
    amber: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300',
    green: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
    red: 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300',
    violet: 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300',
  }
  return (
    <span title={title}
          className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px]
                      font-medium leading-none ${tones[tone]}`}>
      {children}
    </span>
  )
}

export function Btn({ children, onClick, active, disabled, title }: {
  children: React.ReactNode
  onClick?: () => void
  active?: boolean
  disabled?: boolean
  title?: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`rounded px-2.5 py-1 text-xs font-medium transition
        disabled:cursor-not-allowed disabled:opacity-40
        ${active
          ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
          : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'}`}
    >
      {children}
    </button>
  )
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-center text-xs text-slate-400 dark:text-slate-500">{children}</p>
}

export const fmt = (n: number | null | undefined, digits = 0) =>
  n === null || n === undefined || Number.isNaN(n) ? '—' : n.toLocaleString(undefined, {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  })

export const pct = (n: number | null | undefined, digits = 1) =>
  n === null || n === undefined || Number.isNaN(n) ? '—' : `${n.toFixed(digits)}%`
