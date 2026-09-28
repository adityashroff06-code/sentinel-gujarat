import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import { Link } from 'react-router-dom'
import { api, deptColor } from '../lib/api.js'
import { formatTs } from '../lib/time.js'
import { EvidenceLightbox } from './AlertCard.jsx'
import { MatchChip, ProvenanceBadge, SeverityWord } from './Badges.jsx'

// The alert moment (S7.3): a global toast, mounted once in Shell, so a
// watchlist hit is announced on EVERY signed-in screen — the Live Wall
// included — with its evidence frame (S7.2, F73).
//
// Only alerts that arrive after the page loaded are toasted, never the
// backlog: this component opens its own EventSource without a
// Last-Event-ID (the server then sends only rows committed after the
// subscription), and also ignores any alert_seq at or below the newest one
// that existed at mount. Up to 3 stack top-right, 8 s each or until
// dismissed; the stack sits below the header, the status strip and the
// Live Wall's controls, so it never covers them. A two-tone WebAudio chime
// (generated in code, no file, no dependency) sounds for high/critical
// only, with a mute toggle in the header remembered in localStorage.

const TOAST_MS = 8000
const MAX_TOASTS = 3
const CHIME_SEVERITIES = new Set(['high', 'critical'])
const MUTE_KEY = 'sentinel.chime.muted'
const CLEAR_SELECTORS = ['.header', '.status-strip', '.wall-ctrl']

// ---- mute preference: one tiny store shared by the header toggle and the
// toast (localStorage can throw in private windows — never fatal) ----------

const muteListeners = new Set()

function readMuted() {
  try {
    return window.localStorage.getItem(MUTE_KEY) === '1'
  } catch {
    return false
  }
}

let muted = readMuted()

function setMuted(value) {
  muted = value
  try {
    window.localStorage.setItem(MUTE_KEY, value ? '1' : '0')
  } catch {
    // storage unavailable: the choice lasts for this page only
  }
  for (const l of muteListeners) l()
}

function subscribeMuted(listener) {
  muteListeners.add(listener)
  return () => muteListeners.delete(listener)
}

function useChimeMuted() {
  return useSyncExternalStore(subscribeMuted, () => muted)
}

/** The header's mute toggle for the alert chime. */
export function ChimeToggle() {
  const isMuted = useChimeMuted()
  return (
    <button
      type="button"
      className="ghost chime-toggle"
      aria-pressed={!isMuted}
      title="Sound a chime for high and critical alerts"
      onClick={() => setMuted(!isMuted)}
    >
      Chime {isMuted ? 'off' : 'on'}
    </button>
  )
}

// ---- the chime: two short tones, ~250 ms, built in code ------------------

let audioCtx = null

function ensureAudio() {
  const Ctx = window.AudioContext || window.webkitAudioContext
  if (!Ctx) return null
  if (!audioCtx) audioCtx = new Ctx()
  // browsers allow sound only after a user gesture; resume() is refused
  // (and rejects) until then — the toast itself still shows
  if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {})
  return audioCtx
}

let lastChimeAt = 0
const CHIME_GAP_MS = 1500

function chime() {
  try {
    const ctx = ensureAudio()
    // not allowed to sound yet (no click on this page): skip, never queue —
    // a suspended context plays every queued tone at once on the first click
    if (!ctx || ctx.state !== 'running') return
    const nowMs = Date.now()
    if (nowMs - lastChimeAt < CHIME_GAP_MS) return // a burst chimes once
    lastChimeAt = nowMs
    const t0 = ctx.currentTime
    for (const [freq, at] of [
      [880, 0],
      [660, 0.13],
    ]) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.0001, t0 + at)
      gain.gain.exponentialRampToValueAtTime(0.2, t0 + at + 0.015)
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + at + 0.115)
      osc.connect(gain).connect(ctx.destination)
      osc.start(t0 + at)
      osc.stop(t0 + at + 0.12)
    }
  } catch {
    // no audio device, or audio blocked: the toast is the signal
  }
}

// ---- one toast ----------------------------------------------------------

function Toast({ alert: a, onDismiss, onView }) {
  const isZone = a.kind === 'zone'
  const thumb = a.evidence_url || a.crop_url
  const title = isZone ? `ZONE ${a.zone_id ?? ''}`.trim() : a.plate
  return (
    <div
      className={`toast sev-${a.severity || 'low'}`}
      role="status"
      data-alert-id={a.alert_id}
    >
      <div className="toast-bar">
        <SeverityWord severity={a.severity} />
        <span className="toast-kind">{isZone ? 'Zone alert' : 'Watchlist hit'}</span>
        <button
          type="button"
          className="toast-close"
          aria-label={`Dismiss ${a.alert_id}`}
          onClick={onDismiss}
        >
          ×
        </button>
      </div>
      <div className="toast-body">
        {thumb && (
          <img
            className="toast-thumb"
            src={thumb}
            alt={a.evidence_url ? `evidence for ${title}` : `crop for ${title}`}
          />
        )}
        <div className="toast-text">
          <b className={isZone ? 'mono' : 'plate toast-plate'}>{title}</b>
          <div className="toast-line">
            {a.category && <span>{String(a.category).replace(/_/g, ' ')}</span>}
            {!isZone && <MatchChip matchType={a.match_type} distance={a.match_distance} />}
          </div>
          <div className="toast-line muted">
            <span className="mono">{a.camera_id}</span>
            {a.department && (
              <span style={{ color: deptColor(a.department) }}>{a.department}</span>
            )}
          </div>
          <div className="toast-line muted">
            <span className="num">{formatTs(a.fired_at)}</span>
            <ProvenanceBadge clockSource={a.clock_source} />
          </div>
        </div>
      </div>
      <div className="toast-actions">
        {a.evidence_url ? (
          <button type="button" className="chip" onClick={onView}>
            View
          </button>
        ) : (
          <Link className="chip" to="/alerts" onClick={onDismiss}>
            View
          </Link>
        )}
        {!isZone && a.plate && (
          <Link
            className="chip"
            to={`/route/${encodeURIComponent(a.plate)}`}
            onClick={onDismiss}
          >
            Route ›
          </Link>
        )}
      </div>
    </div>
  )
}

// ---- the stack ----------------------------------------------------------

export default function AlertToast() {
  const [toasts, setToasts] = useState([])
  const [viewing, setViewing] = useState(null)
  const [top, setTop] = useState(null)
  const isMuted = useChimeMuted()
  const mutedRef = useRef(isMuted)
  mutedRef.current = isMuted
  const timers = useRef(new Map())

  const dismiss = useCallback((seq) => {
    setToasts((cur) => cur.filter((t) => Number(t.alert_seq) !== seq))
    clearTimeout(timers.current.get(seq))
    timers.current.delete(seq)
  }, [])

  useEffect(() => {
    let alive = true
    let baseline = null // the newest alert_seq when the page loaded
    const pending = []
    const seen = new Set()
    const timersNow = timers.current
    let es = null
    let retry = null
    let attempt = 0
    let hadError = false

    function accept(row) {
      if (baseline === null) pending.push(row)
      else consider(row)
    }

    function consider(row) {
      const seq = Number(row.alert_seq)
      if (!alive || seen.has(seq) || seq <= baseline) return
      seen.add(seq)
      setToasts((cur) => {
        const next = [row, ...cur]
        for (const dropped of next.slice(MAX_TOASTS)) {
          const s = Number(dropped.alert_seq)
          clearTimeout(timersNow.get(s))
          timersNow.delete(s)
        }
        return next.slice(0, MAX_TOASTS)
      })
      timersNow.set(seq, setTimeout(() => dismiss(seq), TOAST_MS))
      if (CHIME_SEVERITIES.has(row.severity) && !mutedRef.current) chime()
    }

    api
      .alerts({ limit: 50 })
      .then((rows) => {
        baseline = rows.reduce((m, r) => Math.max(m, Number(r.alert_seq)), 0)
      })
      .catch(() => {
        // the stream itself never replays the backlog; 0 keeps it working
        baseline = 0
      })
      .finally(() => {
        for (const row of pending.splice(0)) consider(row)
      })

    // Alerts committed while the stream was down. The server sends no
    // event id before the first alert, so a reconnect cannot ask it to
    // replay the gap; the list is read instead (seen/baseline dedupe it).
    function catchUp() {
      api
        .alerts({ limit: 50 })
        .then((rows) => {
          for (const row of [...rows].reverse()) accept(row)
        })
        .catch(() => {
          // reported on the status strip by the data layer
        })
    }

    function connect() {
      es = new EventSource(api.alertStreamUrl)
      es.addEventListener('alert', (e) => {
        let row
        try {
          row = JSON.parse(e.data)
        } catch (err) {
          console.error('unparseable alert frame', err)
          return
        }
        accept(row)
      })
      es.onopen = () => {
        attempt = 0
        if (hadError) {
          hadError = false
          catchUp()
        }
      }
      es.onerror = () => {
        hadError = true
        // a reconnect answered with a non-2xx (the API restarting behind
        // the tunnel, an expired session) closes an EventSource for good:
        // re-open it, backing off 2 s · 2^n, capped at 30 s, × 0.5–1.5
        if (alive && es.readyState === EventSource.CLOSED) {
          es.close()
          const delay = Math.min(30000, 2000 * 2 ** attempt) * (0.5 + Math.random())
          attempt += 1
          retry = setTimeout(() => {
            if (alive) connect()
          }, delay)
        }
      }
    }
    connect()

    // any click unlocks audio for the rest of the page (autoplay policy)
    const unlock = () => {
      try {
        ensureAudio()
      } catch {
        // no audio support: nothing to unlock
      }
    }
    window.addEventListener('pointerdown', unlock, { once: true })

    return () => {
      alive = false
      clearTimeout(retry)
      es?.close()
      window.removeEventListener('pointerdown', unlock)
      for (const t of timersNow.values()) clearTimeout(t)
      timersNow.clear()
    }
  }, [dismiss])

  // sit below whatever chrome this screen has, so the stack never covers
  // the header, the status strip or the Live Wall's grid controls. Those
  // appear late (the lazy wall, its skeleton, a strip that mounts on an
  // error), so the offset is re-measured on any DOM change while a toast
  // shows, at most once a frame.
  const hasToasts = toasts.length > 0
  useLayoutEffect(() => {
    if (!hasToasts) return undefined
    let frame = null
    function measure() {
      let bottom = 0
      for (const sel of CLEAR_SELECTORS) {
        const el = document.querySelector(sel)
        if (el) bottom = Math.max(bottom, el.getBoundingClientRect().bottom)
      }
      setTop(Math.round(bottom) + 8)
    }
    function schedule() {
      if (frame == null) {
        frame = requestAnimationFrame(() => {
          frame = null
          measure()
        })
      }
    }
    measure()
    const observer = new MutationObserver(schedule)
    observer.observe(document.querySelector('.app') || document.body, {
      childList: true,
      subtree: true,
    })
    window.addEventListener('resize', schedule)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', schedule)
      if (frame != null) cancelAnimationFrame(frame)
    }
  }, [hasToasts])

  return (
    <>
      {toasts.length > 0 && (
        <div
          className="toast-stack"
          aria-live="polite"
          aria-label="New alerts"
          style={top != null ? { top } : undefined}
        >
          {toasts.map((a) => (
            <Toast
              key={a.alert_seq}
              alert={a}
              onDismiss={() => dismiss(Number(a.alert_seq))}
              onView={() => setViewing(a)}
            />
          ))}
        </div>
      )}
      {viewing && <EvidenceLightbox alert={viewing} onClose={() => setViewing(null)} />}
    </>
  )
}
