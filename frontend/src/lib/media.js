// Media capability probes shared by the wall tiles and Command's tile pick.

const HEVC_PROBE = 'video/mp4; codecs="hvc1.1.6.L123.B0"'

/** True when this browser's MediaSource can play H.265 (hvc1). */
export function browserDecodesHevc() {
  try {
    return Boolean(window.MediaSource?.isTypeSupported?.(HEVC_PROBE))
  } catch {
    return false // no MSE at all: the HLS path below reports it
  }
}
