/**
 * Express + WebSocket server for the replay viewer.
 *
 * REST is for things the browser asks once (which runs exist, a run's metrics). The
 * WebSocket carries the event stream and the transport controls, so live-following a run
 * in progress and replaying a finished one use the exact same code path on both sides.
 */

import express from 'express'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { WebSocketServer } from 'ws'
import chokidar from 'chokidar'

import { RUNS_DIR, buildTimeline, currentRun, listRuns, periodIndex, readEvents,
         readLinesAt, readMeta, readMetrics } from './runs.js'
import { HEAVY, cacheStats, lite, loadRun } from './logcache.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DIST = path.join(__dirname, '..', 'dist')
const HOST = process.env.PS1982_HOST || '127.0.0.1'
const PORT = Number(process.env.PS1982_PORT || 8100)
const CHUNK = 400
/** Model calls one `detail` request may fetch — a turn has ~12, so this is generous. */
const DETAIL_MAX = 64

const app = express()

app.get('/api/runs', (_req, res) => {
  res.json({ runs: listRuns(), current: currentRun(), runsDir: RUNS_DIR })
})

// What the log cache is actually holding. The point of the cache is that N viewers of one
// run cost one parsed copy, and `retainedMB` against `runs` is the only way to see that
// from outside without attaching a profiler.
app.get('/api/health', (_req, res) => {
  const mem = process.memoryUsage()
  res.json({
    ok: true,
    cache: cacheStats(),
    heapMB: +(mem.heapUsed / 1048576).toFixed(1),
    rssMB: +(mem.rss / 1048576).toFixed(1),
    uptimeS: Math.round(process.uptime()),
  })
})

// A runId is now any number of path segments ("m3/m3_paper_0/<stamp>" as well as the old
// "paper/<stamp>"), so these cannot be `:name/:stamp` — that pattern matched exactly two
// and a grouped run fell through to the SPA catch-all, which answered the metrics request
// with the index page instead of a 404. Take the whole tail and let readMeta/readMetrics
// do the validation; they already reject anything that could climb out of runs/.
const runIdOf = (req) => req.params[0].replace(/\/(meta|metrics)$/, '')

app.get(/^\/api\/runs\/(.+)\/meta$/, (req, res) => {
  const meta = readMeta(runIdOf(req))
  meta ? res.json(meta) : res.status(404).json({ error: 'no meta for this run' })
})

app.get(/^\/api\/runs\/(.+)\/metrics$/, (req, res) => {
  const m = readMetrics(runIdOf(req))
  m ? res.json(m) : res.status(404).json({ error: 'no metrics for this run — run: ps1982 metrics --run <log>' })
})

if (fs.existsSync(DIST)) {
  app.use(express.static(DIST))
  app.get('*', (_req, res) => res.sendFile(path.join(DIST, 'index.html')))
} else {
  app.get('*', (_req, res) =>
    res.status(503).send('<h1>ps1982 viewer</h1><p>The bundle is not built yet. Run <code>npm run build</code> in web/.</p>'))
}

const server = app.listen(PORT, HOST, () => {
  console.log(`ps1982 viewer  http://${HOST}:${PORT}`)
  console.log(`reading runs from ${RUNS_DIR}`)
})

// ---------------------------------------------------------------- websocket

// The event stream is JSON over a link the browser opened; it compresses about 8x, which
// on the biggest run is the difference between pushing 10 MB and pushing 1.3 MB. Caddy's
// `encode` cannot do this — a WebSocket is an upgrade, not a response it gets to encode.
const wss = new WebSocketServer({
  server,
  path: '/ws',
  perMessageDeflate: {
    threshold: 1024,                  // below this, framing costs more than it saves
    zlibDeflateOptions: { level: 6 },
    concurrencyLimit: 10,             // cap zlib work on a 2-core box
  },
})

class Session {
  constructor(ws) {
    this.ws = ws
    this.runId = null
    this.file = null
    this.events = []
    /** Byte offset of each event's line, so a turn's prompts can be re-read on demand. */
    this.offsets = []
    this.timeline = []
    this.periods = []
    // Two-level cursor: `cursor` walks turns, `sub` walks the events inside one turn.
    // Playback and the slider move `cursor`; the arrow keys move `sub` and roll over into
    // the neighbouring turn, so one key walks the whole log linearly.
    this.cursor = 0
    this.sub = 0
    this.offset = 0
    this.playing = false
    this.speed = 1
    this.timer = null
    this.watcher = null
  }

  send(msg) {
    if (this.ws.readyState === 1) this.ws.send(JSON.stringify(msg))
  }

  async load(runId) {
    // A finished run is handed out from the shared cache by reference; a live one is read
    // privately because follow() appends to these arrays as the file grows and every other
    // viewer would see the mutation.
    const live = currentRun() === runId
    const entry = await loadRun(runId, { cache: !live })
    if (!entry) return this.send({ type: 'error', message: `no such run: ${runId}` })
    this.stop()
    this.closeWatcher()
    this.runId = runId
    this.file = entry.file
    this.cursor = 0
    this.sub = 0

    this.events = entry.events
    this.offsets = entry.offsets
    this.timeline = entry.timeline
    this.periods = entry.periods
    this.offset = entry.end
    this.send({
      type: 'loaded',
      runId,
      meta: readMeta(runId),
      metrics: readMetrics(runId),
      totalEvents: this.events.length,
      timeline: this.timeline,
      periods: this.periods,
      live,
    })
    for (let i = 0; i < this.events.length; i += CHUNK) {
      this.send({ type: 'events', events: this.events.slice(i, i + CHUNK) })
    }
    this.send({ type: 'ready', cursor: this.cursor, sub: this.sub })
    if (live) this.follow()
  }

  /**
   * The prompt and reasoning text for one turn's model calls, read straight off disk at the
   * offsets recorded during load. Requested when the raw-record panel is opened, which is
   * the only place these fields are shown.
   *
   * Bounded per request: a turn has a dozen model calls at most, so a range asking for
   * hundreds is not a viewer navigating and is not served as one.
   */
  detail(from, to) {
    const lo = Math.max(0, Math.trunc(from) || 0)
    const hi = Math.min(this.events.length - 1, Math.trunc(to) || 0)
    const want = []
    for (let i = lo; i <= hi && want.length <= DETAIL_MAX; i++) {
      if (this.events[i]?.type === 'model_turn' && this.events[i].payload?.detail) want.push(i)
    }
    if (want.length > DETAIL_MAX) {
      return this.send({ type: 'error', message: `detail range too wide (>${DETAIL_MAX} calls)` })
    }
    const lines = readLinesAt(this.file, want.map((i) => this.offsets[i]))
    const items = []
    for (const i of want) {
      const full = lines.get(this.offsets[i])
      if (!full?.payload) continue
      // Keyed by event_id, not by array position: the client holds these across seeks and
      // an id survives a reload that a position would not.
      const d = { id: full.event_id ?? this.events[i].event_id }
      for (const k of HEAVY) if (full.payload[k] != null) d[k] = full.payload[k]
      items.push(d)
    }
    this.send({ type: 'detail', items })
  }

  /** Tail a run that is still being written: new lines are pushed as they land. */
  follow() {
    this.watcher = chokidar.watch(this.file, { ignoreInitial: true })
    const pull = async () => {
      const before = this.events.length
      this.offset = await readEvents(this.file, {
        start: this.offset,
        // Strip exactly as the initial load did, or a followed run would start pushing the
        // full prompts again the moment it grew.
        onBatch: (b, offs) => {
          for (let i = 0; i < b.length; i++) {
            this.events.push(lite(b[i]).event)
            this.offsets.push(offs[i])
          }
        },
      })
      if (this.events.length === before) return
      this.timeline = buildTimeline(this.events)
      this.periods = periodIndex(this.timeline)
      this.send({ type: 'events', events: this.events.slice(before) })
      this.send({
        type: 'grew',
        totalEvents: this.events.length,
        timeline: this.timeline,
        periods: this.periods,
      })
    }
    this.watcher.on('change', () => { pull().catch(() => {}) })
  }

  closeWatcher() {
    this.watcher?.close()
    this.watcher = null
  }

  /** Emit the cursor position; the browser holds all events and renders up to it. */
  emitCursor() {
    const t = this.timeline[this.cursor]
    this.send({
      type: 'cursor',
      cursor: this.cursor,
      sub: this.sub,
      eventIndex: t?.subs?.[this.sub] ?? t?.to ?? 0,
    })
  }

  nSubs(cursor) {
    return Math.max(1, this.timeline[cursor]?.subs?.length ?? 1)
  }

  clampTurn(c) {
    return Math.max(0, Math.min(this.timeline.length - 1, c))
  }

  /**
   * Step by whole turns, landing on the turn COMPLETED — `sub` goes to the last sub-step,
   * not the first. Otherwise playback would render every turn before its own decision took
   * effect, leaving the market panels a turn behind the header.
   */
  stepTurn(n) {
    this.cursor = this.clampTurn(this.cursor + n)
    this.sub = this.nSubs(this.cursor) - 1
    this.emitCursor()
    return this.cursor
  }

  /**
   * Step by sub-step, rolling over turn boundaries. Walking off the end of a turn lands on
   * the next turn's first sub-step, and walking off the front lands on the previous turn's
   * last — so holding one arrow key traverses the entire session in reading order.
   */
  stepSub(n) {
    const dir = Math.sign(n)
    for (let k = 0; k < Math.abs(n); k++) {
      if (dir > 0) {
        if (this.sub + 1 < this.nSubs(this.cursor)) this.sub++
        else if (this.cursor < this.timeline.length - 1) { this.cursor++; this.sub = 0 }
        else break
      } else {
        if (this.sub > 0) this.sub--
        else if (this.cursor > 0) { this.cursor--; this.sub = this.nSubs(this.cursor) - 1 }
        else break
      }
    }
    this.emitCursor()
    return this.cursor
  }

  /** `sub < 0` means "the end of that turn", which is what dragging the slider should show. */
  seek(c, sub = -1) {
    this.cursor = this.clampTurn(Math.floor(c))
    const last = this.nSubs(this.cursor) - 1
    this.sub = sub < 0 ? last : Math.max(0, Math.min(last, Math.floor(sub)))
    this.emitCursor()
  }

  play() {
    if (this.playing) return
    this.playing = true
    this.send({ type: 'playing', playing: true })
    const tick = () => {
      if (!this.playing) return
      if (this.stepTurn(1) >= this.timeline.length - 1) return this.stop()
      this.timer = setTimeout(tick, Math.max(30, 320 / this.speed))
    }
    this.timer = setTimeout(tick, Math.max(30, 320 / this.speed))
  }

  stop() {
    this.playing = false
    clearTimeout(this.timer)
    this.timer = null
    this.send({ type: 'playing', playing: false })
  }

  dispose() {
    this.stop()
    this.closeWatcher()
  }
}

wss.on('connection', (ws) => {
  const s = new Session(ws)
  s.send({ type: 'hello', runs: listRuns(), current: currentRun() })

  ws.on('message', async (raw) => {
    let msg
    try {
      msg = JSON.parse(raw.toString())
    } catch {
      return
    }
    try {
      switch (msg.type) {
        case 'load': return await s.load(msg.runId)
        case 'detail': return s.detail(msg.from ?? 0, msg.to ?? 0)
        case 'play': return s.play()
        case 'pause': return s.stop()
        case 'step':
          return void (msg.unit === 'sub' ? s.stepSub(msg.n ?? 1) : s.stepTurn(msg.n ?? 1))
        case 'seek': return s.seek(msg.cursor ?? 0, msg.sub ?? -1)
        case 'speed': return void (s.speed = Math.max(0.25, Math.min(16, msg.speed ?? 1)))
        case 'refresh': return s.send({ type: 'hello', runs: listRuns(), current: currentRun() })
        default: return
      }
    } catch (err) {
      s.send({ type: 'error', message: String(err?.message ?? err) })
    }
  })

  ws.on('close', () => s.dispose())
})
