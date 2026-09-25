import { browserDecodesHevc } from '../lib/media.js'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
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
// Relay lane (25 Sep): every camera plays through the relay, so the tile
// says WHICH path it is showing — a source badge from
// GET /api/hls/{cam}/source, kept current from the X-Sentinel-Source
// header on every playlist — and speaks operator words for every state
// (connecting, stalled, local feed offline, CDN not answering, no source,
// H.265 in a browser that cannot decode it). Never a blank black tile.

const noRetry = () => ({ maxNumRetry: 0, retryDelayMs: 0, maxRetryDelayMs: 0 })
const loadPolicy = (firstByteMs, totalMs) => ({
  default: {
    maxTimeToLoadMs: firstByteMs,
    maxLoadTimeMs: totalMs,
    timeoutRetry: noRetry(),
    errorRetry: noRetry(),
  },
})
// Playlists wait longer than segments: a CDN camera's first playlist is a
// login plus the full VOD playlist upstream (~15 s measured 25 Sep), and
// mediamtx's first index blocks ~5 s while its muxer starts.
const PLAYLIST_POLICY = () => loadPolicy(30000, 40000)
const SEGMENT_POLICY = () => loadPolicy(15000, 20000)

const RETRY_BASE_MS = 4000
const RETRY_CAP_MS = 30000
const STALL_MS = 8000

// What each relay path is called on the wall. A CDN recording is never
// labelled LIVE (it is the organisers' recording on the shared timeline).
const SOURCE_BADGE = {
  tee: { text: 'LIVE · RTSP', cls: 'src-live', title: "the analytics worker's own RTSP pull" },
  'stale-tee': {
    text: 'RTSP · RECONNECTING',
    cls: 'src-stale',
    title: "the analytics worker is reconnecting — showing its last good seconds",
  },
  mediamtx: {
    text: 'LOCAL FEED',
    cls: 'src-local',
    title: 'our own filmed feed, replayed over RTSP and relayed',
  },
  cdn: {
    text: 'CDN RECORDING',
    cls: 'src-cdn',
    title: "the organisers' HLS recording at the shared-timeline position, relayed",
  },
}

// Measured 25 Sep on the demo laptop: Google Chrome 122 decodes hvc1
// through MSE (hardware, headed); Edge 153 does not (it needs Windows'
// HEVC Video Extensions). So the tile names Chrome, and the tooltip says
// what Edge needs.
const HEVC_WORD = 'H.265 feed — this browser cannot decode HEVC; open the wall in Google Chrome'
const HEVC_DETAIL =
  'MediaSource cannot play hvc1 here. Chrome decodes H.265 with hardware support; ' +
  'Edge needs the HEVC Video Extensions from the Microsoft Store.'


// Operator words for a failure: the HTTP status the relay answered (when
// there was one) plus the path it was on. Raw hls.js detail strings
// ('manifestLoadTimeOut') stay on the tooltip only (S3.3b).
function failureWords(status, source, hlsDetail = '') {
  if (status === 401) return 'Session expired — sign in again'
  if (status === 429) return 'Too many open streams — slowing down'
  if (status === 404) return 'No live source for this camera'
  if (status === 503 || status === 502) {
    if (source === 'mediamtx') return 'Local feed offline'
    if (source === 'cdn') return "Organisers' CDN not answering"
    return 'Feed reconnecting'
  }
  if (/manifest|level/i.test(hlsDetail)) return 'No signal'
  if (/frag|buffer/i.test(hlsDetail)) return 'Stream interrupted'
  if (/media|codec|decod/i.test(hlsDetail)) return 'Cannot decode this stream'
  return 'Stream error'
}

function responseDetail(networkDetails) {
  // the relay's JSON {"detail": "..."} — machine-readable, tooltip only
  try {
    const text = networkDetails?.responseText
    if (text) return JSON.parse(text)?.detail || ''
  } catch {
    // binary (segment) responses have no text body: nothing to add
  }
  return ''
}

function headerSource(networkDetails) {
  try {
    return networkDetails?.getResponseHeader?.('X-Sentinel-Source') || null
  } catch {
    return null
  }
}

export default function Tile({ cam, expandable = true }) {
  const videoRef = useRef(null)
  const [state, setState] = useState({ kind: 'connecting', word: 'Connecting…' })
  const [source, setSource] = useState(null) // {source, detail}
  const [gen, setGen] = useState(0) // bumping it re-creates the player
  const attemptsRef = useRef(0)
  const isHevc = String(cam.codec || '').toLowerCase() === 'hevc'

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
    let stallTimer = null
    let mediaRecoveries = 0
    let lastSource = null

    setState({ kind: 'connecting', word: 'Connecting…' })

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

    const noteSource = (s, detail) => {
      if (disposed || !s) return
      lastSource = s
      setSource((prev) =>
        prev && prev.source === s && (detail === undefined || prev.detail === detail)
          ? prev
          : { source: s, detail: detail ?? prev?.detail ?? '' }
      )
    }

    const scheduleRetry = (word, detail) => {
      if (disposed || retryTimer) return
      const attempt = attemptsRef.current
      attemptsRef.current = attempt + 1
      const delay =
        Math.min(RETRY_BASE_MS * 2 ** attempt, RETRY_CAP_MS) * (0.5 + Math.random())
      setState({
        kind: 'error',
        word: `${word} — retrying in ${Math.max(1, Math.round(delay / 1000))} s`,
        detail,
      })
      retryTimer = setTimeout(() => {
        retryTimer = null
        if (!disposed) setGen((g) => g + 1)
      }, delay)
    }

    const onPlaying = () => {
      if (disposed) return
      clearTimeout(stallTimer)
      stallTimer = null
      attemptsRef.current = 0 // the feed answered — reset the ladder
      setState(null)
    }
    const onWaiting = () => {
      if (disposed || stallTimer) return
      stallTimer = setTimeout(() => {
        stallTimer = null
        if (!disposed) {
          setState({ kind: 'stalled', word: 'Feed stalled — waiting for video', detail: 'buffer empty' })
        }
      }, STALL_MS)
    }
    const onNativeError = () => {
      if (disposed) return
      scheduleRetry('Stream error', video.error?.message || 'native playback error')
    }
    video.addEventListener('playing', onPlaying)
    video.addEventListener('waiting', onWaiting)

    const startPlayer = () => {
      if (disposed) return
      if (Hls.isSupported()) {
        hls = new Hls({
          enableWorker: true, // transmux off the main thread (CSP worker-src blob:)
          lowLatencyMode: false,
          maxBufferLength: 12, // 16 tiles on an 8 GB laptop: keep buffers small
          backBufferLength: 6,
          manifestLoadPolicy: PLAYLIST_POLICY(),
          playlistLoadPolicy: PLAYLIST_POLICY(),
          fragLoadPolicy: SEGMENT_POLICY(),
        })
        const fromHeader = (_e, data) => noteSource(headerSource(data?.networkDetails))
        hls.on(Hls.Events.MANIFEST_LOADED, fromHeader)
        hls.on(Hls.Events.LEVEL_LOADED, fromHeader)
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          if (disposed) return
          video.play?.().catch(() => {
            // autoplay of a muted video is allowed everywhere we target;
            // if a policy still blocks it, the stall overlay says so
          })
        })
        hls.on(Hls.Events.ERROR, (_e, data) => {
          if (disposed || !data.fatal) return
          if (data.type === Hls.ErrorTypes.MEDIA_ERROR && isHevc && !browserDecodesHevc()) {
            // an H.265 stream this browser cannot decode: say so, once —
            // retrying would fail the same way forever
            killPlayer()
            setState({ kind: 'blocked', word: HEVC_WORD, detail: HEVC_DETAIL })
            return
          }
          if (data.type === Hls.ErrorTypes.MEDIA_ERROR && mediaRecoveries < 2) {
            mediaRecoveries += 1
            hls.recoverMediaError()
            return
          }
          const status = data.response?.code ?? data.networkDetails?.status ?? 0
          const why = responseDetail(data.networkDetails) || data.details || 'stream error'
          killPlayer()
          scheduleRetry(failureWords(status, lastSource, data.details), why)
        })
        hls.loadSource(src)
        hls.attachMedia(video)
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = src // Safari native HLS
        // the native path needs its own error handling or a dead feed is a
        // silent black tile labelled LIVE (frontend/CLAUDE.md: never silent)
        video.addEventListener('error', onNativeError)
      } else {
        setState({
          kind: 'blocked',
          word: 'Live view is not supported in this browser — open the wall in Google Chrome',
          detail: 'no Media Source Extensions',
        })
      }
    }

    // Ask the relay which path this camera takes before pulling anything:
    // a camera with no source never requests a playlist, and neither does
    // an H.265 camera served from its worker's tee (a stream copy of the
    // RTSP, so certainly H.265) in a browser that cannot decode it. The
    // registry codec comes from the RTSP probe; the organisers' CDN copy
    // may be re-encoded (cam08's was 854x480), so a CDN tile is tried and
    // only a decode failure shows the H.265 message.
    api
      .hlsSource(cam.camera_id)
      .then((s) => {
        if (disposed) return
        noteSource(s.source, s.detail)
        if (s.source === 'none') {
          scheduleRetry('No live source for this camera', s.detail)
          return
        }
        const teeCopy = s.source === 'tee' || s.source === 'stale-tee'
        if (isHevc && teeCopy && !browserDecodesHevc()) {
          setState({ kind: 'blocked', word: HEVC_WORD, detail: HEVC_DETAIL })
          return
        }
        startPlayer()
      })
      .catch((e) => {
        if (disposed) return
        scheduleRetry(failureWords(e?.status, lastSource), e?.detail || 'source lookup failed')
      })

    return () => {
      disposed = true
      if (retryTimer) clearTimeout(retryTimer)
      if (stallTimer) clearTimeout(stallTimer)
      killPlayer()
      video.removeEventListener('error', onNativeError)
      video.removeEventListener('playing', onPlaying)
      video.removeEventListener('waiting', onWaiting)
      video.removeAttribute('src')
      video.load()
    }
  }, [cam.camera_id, gen, isHevc])

  const badge = source ? SOURCE_BADGE[source.source] : null
  const dept = cam.department || 'Unknown'
  const where = cam.location_name || ''

  return (
    <div className="tile" data-camera-id={cam.camera_id} data-source={source?.source || ''}>
      <video ref={videoRef} autoPlay muted playsInline aria-label={`${cam.camera_id} live view`} />
      <div className="label">
        <span className="tile-id">
          <span
            className="dept-dot"
            style={{ background: deptColor(cam.department) }}
            title={dept}
            aria-hidden="true"
          />
          <span className="visually-hidden">{dept} department, </span>
          <b className="mono">{cam.camera_id}</b>
          {where && (
            <span className="tile-loc" title={where}>
              {where}
            </span>
          )}
        </span>
        <span className="tile-right">
          {badge && (
            <span className={`src-badge ${badge.cls}`} title={`${badge.title} — ${source.detail}`}>
              {badge.cls === 'src-live' && <span className="dot" aria-hidden="true" />}
              {badge.text}
            </span>
          )}
          {expandable && (
            <Link
              className="tile-expand"
              to={`/wall?cam=${encodeURIComponent(cam.camera_id)}`}
              title={`Open ${cam.camera_id} full size`}
              aria-label={`Open ${cam.camera_id} full size`}
            >
              ⤢
            </Link>
          )}
        </span>
      </div>
      {state && (
        <div className={`tile-state ${state.kind}`} role="status" title={state.detail || ''}>
          <span className="mono">{cam.camera_id}</span>
          <span>{state.word}</span>
        </div>
      )}
    </div>
  )
}
