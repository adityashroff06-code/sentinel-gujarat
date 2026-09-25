import { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import { api, deptColor } from '../lib/api.js'

// One live tile. Mounts an hls.js player on view; FULLY destroys it on
// unmount — a leaked player is a leaked stream pull (frontend/CLAUDE.md:
// only visible tiles hold an open stream). The session cookie carries the
// playlist and segment requests (same origin — decision F41).
// Ported from D:\projects\Sentinel_Repo\ui\src\components\Tile.jsx (F52);
// extended for S3.3: a fatal MEDIA_ERROR gets hls.recoverMediaError()
// (twice, then a full restart), everything else destroys the player and
// re-creates it after a jittered exponential backoff (base 4 s, cap 30 s,
// x random(0.5, 1.5)) — hls.js's own retries are disabled so the tile owns
// the ONE retry policy and a wall of dead feeds never hammers the relay.

const noRetry = () => ({ maxNumRetry: 0, retryDelayMs: 0, maxRetryDelayMs: 0 })
const loadPolicy = () => ({
  default: {
    maxTimeToLoadMs: 10000,
    maxLoadTimeMs: 20000,
    timeoutRetry: noRetry(),
    errorRetry: noRetry(),
  },
})

const RETRY_BASE_MS = 4000
const RETRY_CAP_MS = 30000

export default function Tile({ cam }) {
  const videoRef = useRef(null)
  const [err, setErr] = useState(null)
  const [gen, setGen] = useState(0) // bumping it re-creates the player
  const attemptsRef = useRef(0)

  // a different camera starts a fresh backoff ladder
  useEffect(() => {
    attemptsRef.current = 0
  }, [cam.camera_id])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return undefined
    const src = api.streamUrl(cam.camera_id)
    let disposed = false
    let hls = null
    let hlsDead = false
    let retryTimer = null
    let mediaRecoveries = 0

    const killPlayer = () => {
      if (hls && !hlsDead) {
        hlsDead = true
        try {
          hls.destroy() // tears down the pull entirely
        } catch {
          // already torn down mid-error — nothing left holding a stream
        }
      }
    }

    const scheduleRetry = (reason) => {
      if (disposed || retryTimer) return
      const attempt = attemptsRef.current
      attemptsRef.current = attempt + 1
      const delay =
        Math.min(RETRY_BASE_MS * 2 ** attempt, RETRY_CAP_MS) * (0.5 + Math.random())
      setErr(`${reason} — retrying`)
      retryTimer = setTimeout(() => {
        retryTimer = null
        if (!disposed) setGen((g) => g + 1)
      }, delay)
    }

    if (Hls.isSupported()) {
      hls = new Hls({
        lowLatencyMode: false,
        maxBufferLength: 20,
        manifestLoadPolicy: loadPolicy(),
        playlistLoadPolicy: loadPolicy(),
        fragLoadPolicy: loadPolicy(),
      })
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        if (disposed) return
        attemptsRef.current = 0 // the feed answered — reset the ladder
        setErr(null)
      })
      hls.on(Hls.Events.ERROR, (_e, data) => {
        if (disposed || !data.fatal) return
        if (data.type === Hls.ErrorTypes.MEDIA_ERROR && mediaRecoveries < 2) {
          mediaRecoveries += 1
          hls.recoverMediaError()
          return
        }
        killPlayer()
        scheduleRetry(data.details || 'stream error')
      })
      hls.loadSource(src)
      hls.attachMedia(video)
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src // Safari native HLS
    } else {
      setErr('HLS not supported')
    }

    return () => {
      disposed = true
      if (retryTimer) clearTimeout(retryTimer)
      killPlayer()
      video.removeAttribute('src')
      video.load()
    }
  }, [cam.camera_id, gen])

  return (
    <div className="tile">
      <video ref={videoRef} autoPlay muted playsInline />
      <div className="label">
        <span>
          {cam.camera_id}
          <span
            className="badge"
            style={{ background: deptColor(cam.department), marginLeft: 6 }}
          >
            {cam.department || 'Unknown'}
          </span>
        </span>
        <span className="live">
          <span className="dot" aria-hidden="true" /> LIVE
        </span>
      </div>
      {err && (
        <div className="err">
          {cam.camera_id}: {err}
        </div>
      )}
    </div>
  )
}
