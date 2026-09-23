"""Model weights: download once, SHA-256 pin, verify forever (S2.3; F25).

``ensure()`` returns the path to ``models/yolox_s.onnx``, downloading it on
first use. The first download appends the file's SHA-256 to the root
``CHECKSUMS.txt`` (committed); every later call verifies against that pin
and refuses a mismatch.

CLI (from the repo root): ``python -m ml.tools.fetch_models``
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from backend.core.config import REPO_ROOT
from backend.core.logging_setup import setup

log = setup("fetch_models")

YOLOX_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx"
YOLOX_RELPATH = "models/yolox_s.onnx"
CHECKSUMS = REPO_ROOT / "CHECKSUMS.txt"


class ChecksumMismatch(RuntimeError):
    """The file on disk does not match its pinned SHA-256."""


def sha256_file(path: Path) -> str:
    """Hex SHA-256 of *path*, streamed."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def recorded_sha(relpath: str, checksums: Path | None = None) -> str | None:
    """The pinned SHA-256 for *relpath* (CHECKSUMS.txt third column), or None."""
    checksums = checksums or CHECKSUMS
    if not checksums.is_file():
        return None
    for line in checksums.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == relpath:
            return parts[0]
    return None


def ensure(relpath: str = YOLOX_RELPATH, url: str = YOLOX_URL,
           root: Path | None = None, checksums: Path | None = None) -> Path:
    """Return the verified model path, downloading and pinning on first use.

    Raises :class:`ChecksumMismatch` when the file on disk (or a fresh
    download) does not match the pinned SHA-256 — never silently accepts
    a tampered file.
    """
    root = root or REPO_ROOT
    checksums = checksums or CHECKSUMS
    path = root / relpath
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        log.info("downloading %s -> %s", url, relpath)
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(path)
    sha = sha256_file(path)
    pinned = recorded_sha(relpath, checksums)
    if pinned is None:
        with open(checksums, "a", encoding="utf-8") as f:
            f.write(f"{sha}  {url}  {relpath}\n")
        log.info("pinned %s sha256=%s in %s", relpath, sha, checksums.name)
    elif sha != pinned:
        raise ChecksumMismatch(
            f"{relpath}: sha256 {sha} does not match the pin {pinned} in "
            f"{checksums} — refusing to use it. Delete the file and re-run "
            f"to re-download, or restore the pinned original."
        )
    return path


if __name__ == "__main__":
    p = ensure()
    print(f"{p} OK sha256={sha256_file(p)}")
