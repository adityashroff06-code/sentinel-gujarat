import { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import { api, deptColor } from '../lib/api.js'

// One live tile. Mounts an hls.js player on view; FULLY destroys it on
// unmount — a leaked player is a leaked stream pull (frontend/CLAUDE.md:
// only visible tiles hold an open stream). The session cookie carries the
// playlist and segment requests (same origin — decision F41).
// Ported from D:\projects\Sentinel_Repo\ui\src\components\Tile.jsx (F52);
// wired to the Live Wall in S3.3.
export default function Tile({ cam }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    const video = videoRef.current
    const src = api.streamUrl(cam.camera_id)
    let cancelled = false
    setErr(null)

    if (Hls.isSupported()) {
      const hls = new Hls({ lowLatencyMode: false, maxBufferLength: 20 })
      hlsRef.current = hls
      hls.loadSource(src)
      hls.attachMedia(video)
      hls.on(Hls.Events.ERROR, (_e, data) => {
        if (data.fatal && !cancelled) setErr(data.details || 'stream error')
      })
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src // Safari native HLS
    } else {
      setErr('HLS not supported')
    }

    return () => {
      cancelled = true
      if (hlsRef.current) {
        hlsRef.current.destroy() // tears down the pull entirely
        hlsRef.current = null
      }
      if (video) {
        video.removeAttribute('src')
        video.load()
      }
    }
  }, [cam.camera_id])

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
            {cam.department}
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
