/**
 * Parsed logs, shared between connections, with the bulky prompt text left on disk.
 *
 * Two problems this solves, both measured on runs/rounds/m4_r5_random (107.5 MB, 11,462
 * events):
 *
 *  1. `model_turn` is 93.7% of a log's bytes, and three of its fields — `user` (33.6% of
 *     the file), `system` (30.9%) and `reasoning` (26.1%) — are 90.6% of it between them.
 *     All three are rendered only inside a triple-collapsed panel in AgentTrail, so pushing
 *     them to the browser on load spent 97 MB on something nobody had asked to see. They
 *     are stripped here and re-read one line at a time when a turn is actually opened.
 *     `completion`, the answer itself, is 0.8% and stays.
 *  2. Every WebSocket connection used to parse its own copy: 243 MB of heap for one viewer
 *     on that run, on a 2-core box already running four other services. Entries are keyed
 *     by runId and handed out by reference, so N viewers of one run cost one copy.
 *
 * The live run is deliberately NOT cached. Session.follow() appends to its own array as the
 * file grows, and a shared array would be mutated underneath every other viewer.
 */

import fs from 'node:fs'

import { buildTimeline, logPath, periodIndex, readEvents } from './runs.js'

/** Fields dropped from the pushed copy and re-read on demand. */
export const HEAVY = ['system', 'user', 'reasoning']

/** Retained lite events, across all cached runs. Past this the oldest entry is dropped. */
const MAX_BYTES = 320 * 1024 * 1024
/** A ceiling on entries as well, so many small runs cannot pin unbounded Map overhead. */
const MAX_ENTRIES = 8

/** runId -> entry. Map keeps insertion order, so the first key is the least recently used. */
const entries = new Map()
let totalBytes = 0

/**
 * Strip the heavy fields from a model_turn, returning the lean event and how many bytes of
 * text went away. `detail: true` tells the client the fields exist on disk and can be
 * fetched; it is set only when something was actually removed, so an api_error turn that
 * never had prompts does not advertise a detail that would come back empty.
 */
export function lite(e) {
  if (e?.type !== 'model_turn' || !e.payload) return { event: e, stripped: 0 }
  let stripped = 0
  let payload = null
  for (const k of HEAVY) {
    const v = e.payload[k]
    if (v == null) continue
    if (!payload) payload = { ...e.payload }
    stripped += typeof v === 'string' ? v.length : 0
    delete payload[k]
  }
  if (!payload) return { event: e, stripped: 0 }
  payload.detail = true
  return { event: { ...e, payload }, stripped }
}

function evict() {
  while ((totalBytes > MAX_BYTES || entries.size > MAX_ENTRIES) && entries.size > 1) {
    const oldest = entries.keys().next().value
    const e = entries.get(oldest)
    entries.delete(oldest)
    totalBytes -= e.bytes
  }
}

/** Fresh means same file, same size, same mtime — anything else and we re-read. */
function fresh(entry, stat) {
  return entry && entry.size === stat.size && entry.mtimeMs === stat.mtimeMs
}

/**
 * The lite events, their byte offsets, and the timeline for a run.
 *
 * Returns null for a runId that does not resolve to a readable log. The arrays are SHARED —
 * callers must treat them as read-only.
 */
export async function loadRun(runId, { cache = true } = {}) {
  const file = logPath(runId)
  if (!file) return null
  let stat
  try {
    stat = fs.statSync(file)
  } catch {
    return null
  }

  if (cache) {
    const hit = entries.get(runId)
    if (fresh(hit, stat)) {
      entries.delete(runId)      // move to the most-recent end
      entries.set(runId, hit)
      return hit
    }
    if (hit) {
      entries.delete(runId)
      totalBytes -= hit.bytes
    }
  }

  const events = []
  const offsets = []
  let stripped = 0
  const end = await readEvents(file, {
    onBatch: (batch, offs) => {
      for (let i = 0; i < batch.length; i++) {
        const { event, stripped: n } = lite(batch[i])
        events.push(event)
        offsets.push(offs[i])
        stripped += n
      }
    },
  })

  const timeline = buildTimeline(events)
  const entry = {
    runId, file, offsets, events, timeline,
    periods: periodIndex(timeline),
    end,
    size: stat.size,
    mtimeMs: stat.mtimeMs,
    // What is actually retained: the file minus the text we did not keep. Close enough to
    // budget by, and free — the lengths were summed while stripping.
    bytes: Math.max(0, stat.size - stripped),
  }

  if (cache) {
    entries.set(runId, entry)
    totalBytes += entry.bytes
    evict()
  }
  return entry
}

export function cacheStats() {
  return {
    runs: entries.size,
    retainedMB: +(totalBytes / 1048576).toFixed(1),
    capMB: MAX_BYTES / 1048576,
  }
}

/** Drop everything — only used by tests and by an explicit refresh. */
export function clearCache() {
  entries.clear()
  totalBytes = 0
}
