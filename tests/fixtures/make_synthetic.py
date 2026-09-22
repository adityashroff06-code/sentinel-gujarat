"""Generate the synthetic test clip (decision F20): 60 s, 640×360, 25 fps,
ffmpeg lavfi testsrc2 plus a drawbox moving across the frame. No sandbox
footage is ever downloaded for tests (root rule 6 / F5)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from backend.core import config

CLIP = Path(__file__).resolve().parent / "synthetic_60s.mp4"


def ensure() -> Path:
    """Create the clip if missing; return its path."""
    if CLIP.exists():
        return CLIP
    subprocess.run(
        [
            config.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=60",
            "-vf", "drawbox=x='mod(t*40,600)':y=150:w=40:h=40:color=white@0.9:t=fill",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            str(CLIP),
        ],
        check=True, timeout=180,
    )
    return CLIP


if __name__ == "__main__":
    print(ensure())
