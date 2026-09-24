// ONE shared poller (frontend/CLAUDE.md: not Header and Dashboard polling
// separately). Subscribers sharing a key share one timer and one in-flight
// request; the timer stops when the last subscriber leaves and pauses while
// the tab is hidden.

import { useEffect, useState } from 'react'

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
