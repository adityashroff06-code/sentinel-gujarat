// Media capability probes shared by the wall tiles and Command's tile pick.

const HEVC_PROBE = 'video/mp4; codecs="hvc1.1.6.L123.B0"'

/** True when the MediaSource hls.js will play through can take H.265
 *  (hvc1). Probes the same object, in the same order, as hls.js 1.7's
 *  getMediaSource(): ManagedMediaSource first (iPhone Safari 17.1+ has
 *  only this, no window.MediaSource), then MediaSource, then the prefixed
 *  WebKitMediaSource. No native-HLS fallback on purpose: the worker tee
 *  is HEVC in MPEG-TS, which Safari's native HLS does not play (Apple
 *  requires fMP4 for HEVC), so there the blocked message is the truth. */
export function browserDecodesHevc() {
  try {
    const MS = window.ManagedMediaSource || window.MediaSource || window.WebKitMediaSource
    return Boolean(MS?.isTypeSupported?.(HEVC_PROBE))
  } catch {
    return false // no MSE at all: the HLS path below reports it
  }
}
