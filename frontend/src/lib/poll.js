// ONE shared data layer: the poller (frontend/CLAUDE.md: not Header and
// Dashboard polling separately) and the alert stream hook used by both
// Command and Alerts. Subscribers sharing a key share one timer and one
// in-flight request; the timer stops when the last subscriber leaves and
// pauses while the tab is hidden.

import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'

const channels = new Map() // key -> {fetcher, interval, timer, listeners, last, inflight}

function broadcast(ch) {
  for (const l of ch.listeners) l(ch.last)
}

async function tick(ch) {
  if (ch.inflight || document.hidden) return
  ch.inflight = true
  try {
    const data = await ch.fetcher()
    ch.last = { data, error: null, at: Date.now() }
  } catch (error) {
    ch.last = { data: ch.last?.data ?? null, error, at: Date.now() }
  } finally {
    ch.inflight = false
  }
  broadcast(ch)
}

function onVisible() {
  if (document.hidden) return
  for (const ch of channels.values()) tick(ch)
}
document.addEventListener('visibilitychange', onVisible)

/** Join the shared poll for `key`. `listener` receives {data, error, at}.
 *  Returns an unsubscribe function. */
export function subscribe(key, fetcher, intervalMs, listener) {
  let ch = channels.get(key)
  if (!ch) {
    ch = { fetcher, interval: intervalMs, timer: null, listeners: new Set(), last: null, inflight: false }
    channels.set(key, ch)
    ch.timer = setInterval(() => tick(ch), intervalMs)
    tick(ch)
  }
  ch.listeners.add(listener)
  if (ch.last) listener(ch.last)
  return () => {
    ch.listeners.delete(listener)
    if (ch.listeners.size === 0) {
      clearInterval(ch.timer)
      channels.delete(key)
    }
  }
}

/** React hook over the shared poller: `usePolled('stats', api.stats, 5000)`
 *  -> {data, error, at} (null until the first result arrives). */
export function usePolled(key, fetcher, intervalMs) {
  const [state, setState] = useState(null)
  useEffect(
    () => subscribe(key, fetcher, intervalMs, setState),
    // fetcher identity is keyed by `key`; callers pass stable fetchers
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key, intervalMs]
  )
  return state
}

// ---- live alert stream (SSE) ------------------------------------------------
// One hook for Command and Alerts (only one page is mounted at a time):
// initial fill from GET /api/alerts, then EventSource on /api/alerts/stream
// (the session cookie carries it — decision F41). Newest first, deduped by
// alert_seq, capped. Ports the SSE wiring of the old Dashboard.jsx and
// Alerts.jsx (F52) minus D13: the new backend streams full alert rows for
// BOTH kinds, so no client-side zone re-mapping, and errors are surfaced.

function insertAlert(list, alert, cap) {
  const seq = Number(alert.alert_seq)
  if (list.some((a) => Number(a.alert_seq) === seq)) {
    return list.map((a) => (Number(a.alert_seq) === seq ? { ...a, ...alert } : a))
  }
  const next = [alert, ...list]
  next.sort((a, b) => Number(b.alert_seq) - Number(a.alert_seq))
  return next.slice(0, cap)
}

/** Live alerts, newest first, capped at `cap` (default 200).
 *  Returns {alerts, stream: 'connecting'|'live'|'reconnecting', applyAck}. */
export function useAlertStream(cap = 200) {
  const [alerts, setAlerts] = useState(null) // null = still loading
  const [stream, setStream] = useState('connecting')

  useEffect(() => {
    let alive = true
    api
      .alerts({ limit: cap })
      .then((rows) => {
        if (!alive) return
        setAlerts((cur) => {
          let list = cur ?? []
          for (const row of rows) list = insertAlert(list, row, cap)
          return list
        })
      })
      .catch(() => {
        // the data layer already reported this on the status strip;
        // the page shows its own error state through `alerts === null`
        if (alive) setAlerts((cur) => cur ?? [])
      })

    const es = new EventSource(api.alertStreamUrl)
    es.onopen = () => alive && setStream('live')
    es.onerror = () => alive && setStream('reconnecting') // ES auto-reconnects
    es.addEventListener('alert', (e) => {
      if (!alive) return
      try {
        const row = JSON.parse(e.data)
        setAlerts((cur) => insertAlert(cur ?? [], row, cap))
      } catch (err) {
        // a malformed frame is a bug worth seeing, not swallowing
        console.error('unparseable alert frame', err)
      }
    })
    return () => {
      alive = false
      es.close()
    }
  }, [cap])

  /** Merge an acknowledged row (the POST /ack response) into the list. */
  const applyAck = useCallback((row) => {
    setAlerts((cur) =>
      (cur ?? []).map((a) => (a.alert_seq === row.alert_seq ? { ...a, ...row } : a))
    )
  }, [])

  return { alerts: alerts ?? [], loaded: alerts !== null, stream, applyAck }
}
