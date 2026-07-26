/**
 * Reading the experiment logs.
 *
 * The Python engine writes one append-only JSONL per run; this module is the only place
 * that knows about the filesystem layout. Nothing is transformed here — the browser sees
 * the same event objects the metrics code does.
 */

import fs from 'node:fs'
import path from 'node:path'
import readline from 'node:readline'

export const RUNS_DIR = path.resolve(process.cwd(), '..', 'runs')

/** Runs are grouped in subdirectories now — "m3/m3_paper_0/2026-07-25_223020" as well as
 *  the old flat "paper/2026-07-25_174344" — so a runId is any number of path segments.
 *  Each segment is still restricted to word characters, dots and dashes, which is what
 *  keeps ".." out; the resolved-path check below is the second line of defence. */
const SAFE_RUN_ID = /^[\w.-]+(\/[\w.-]+)+$/

/** "m3/m3_paper_0/2026-07-25_223020" -> absolute .jsonl path */
export function logPath(runId) {
  if (!SAFE_RUN_ID.test(runId) || runId.split('/').includes('..')) return null
  const p = path.resolve(RUNS_DIR, `${runId}.jsonl`)
  return p.startsWith(RUNS_DIR + path.sep) && fs.existsSync(p) ? p : null
}

function sidecar(runId, ext) {
  if (!SAFE_RUN_ID.test(runId) || runId.split('/').includes('..')) return null
  const p = path.resolve(RUNS_DIR, `${runId}.${ext}`)
  if (!p.startsWith(RUNS_DIR + path.sep) || !fs.existsSync(p)) return null
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'))
  } catch {
    return null
  }
}

export const readMeta = (runId) => sidecar(runId, 'meta.json')
export const readMetrics = (runId) => sidecar(runId, 'metrics.json')

/** Every run on disk, newest first. Recurses, so runs can be grouped:
 *    runs/m3/m3_paper_0/2026-07-25_223020.jsonl   -> group "m3", name "m3_paper_0"
 *    runs/paper/2026-07-25_174344.jsonl           -> no group, name "paper"
 *  `name` stays the run's own directory either way, so nothing that displays it changes. */
export function listRuns() {
  if (!fs.existsSync(RUNS_DIR)) return []
  const out = []
  const walk = (dir, rel) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        walk(full, rel ? `${rel}/${entry.name}` : entry.name)
        continue
      }
      if (!entry.name.endsWith('.jsonl') || !rel) continue
      const stamp = entry.name.slice(0, -6)
      const runId = `${rel}/${stamp}`
      const parts = rel.split('/')
      const name = parts[parts.length - 1]
      const group = parts.length > 1 ? parts.slice(0, -1).join('/') : null
      const st = fs.statSync(full)
      const meta = readMeta(runId)
      out.push({
        runId,
        name,
        group,
        stamp,
        bytes: st.size,
        mtime: st.mtimeMs,
        hasMetrics: !!readMetrics(runId),
        sequence: meta?.sequence?.name ?? null,
        agentKinds: [...new Set((meta?.config?.agents ?? []).map((a) => a.kind))],
        sessions: meta?.config?.sessions ?? null,
        totals: meta?.totals ?? null,
      })
    }
  }
  walk(RUNS_DIR, '')
  return out.sort((a, b) => b.mtime - a.mtime)
}

/** How long a log may sit untouched before it stops counting as live. */
const LIVE_STALE_MS = 90_000

/**
 * The run the Python CLI is currently writing, if any.
 *
 * runs/.current names the most recently STARTED run, which is not the same as one still
 * being written — the pointer survives the process. So also require the file to have been
 * touched recently; otherwise a finished run would keep claiming to be live.
 */
export function currentRun() {
  const p = path.join(RUNS_DIR, '.current')
  if (!fs.existsSync(p)) return null
  const id = fs.readFileSync(p, 'utf8').trim()
  const file = logPath(id)
  if (!file) return null
  return Date.now() - fs.statSync(file).mtimeMs < LIVE_STALE_MS ? id : null
}

/**
 * Stream a log line by line, invoking onBatch with arrays of parsed events.
 *
 * A run in progress can leave a partial final line; that line is skipped rather than
 * throwing, and the byte offset returned is the end of the last COMPLETE line so a
 * follower can resume cleanly from there.
 */
export function readEvents(file, { onBatch, batchSize = 500, start = 0 } = {}) {
  return new Promise((resolve, reject) => {
    const stream = fs.createReadStream(file, { encoding: 'utf8', start })
    const rl = readline.createInterface({ input: stream, crlfDelay: Infinity })
    let batch = []
    let consumed = start
    let pending = 0

    rl.on('line', (line) => {
      const bytes = Buffer.byteLength(line, 'utf8') + 1
      pending += bytes
      const t = line.trim()
      if (!t) {
        consumed += pending
        pending = 0
        return
      }
      try {
        batch.push(JSON.parse(t))
      } catch {
        return // truncated tail: leave `consumed` behind it so we retry this line later
      }
      consumed += pending
      pending = 0
      if (batch.length >= batchSize) {
        onBatch?.(batch)
        batch = []
      }
    })
    rl.on('close', () => {
      if (batch.length) onBatch?.(batch)
      resolve(consumed)
    })
    rl.on('error', reject)
  })
}

// The playback timeline lives in timeline.js — a session takes hours of wall-clock, so
// replay is paced by turn rather than by the recorded timestamps. Re-exported here because
// index.js already imports its log-reading helpers from this module.
export { buildTimeline, periodIndex } from './timeline.js'
