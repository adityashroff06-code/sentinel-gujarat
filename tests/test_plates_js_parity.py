"""The Search preview's JS grammar mirror (frontend/src/lib/plates.js) agrees
with backend/core/plates.py — the one implementation (B10) — on every case.

Runs the ES module under node; skipped where node is not installed.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.core import plates

JS = Path(__file__).resolve().parent.parent / "frontend" / "src" / "lib" / "plates.js"

FIXED = [
    "6J23H1548", "GJ23H1548", "GJ1157924", "GJ11S7924", "GJO3XH0407", "GJ03XH0407",
    "GJ01AB1234", "GJ01A81234", "gj 01 ab 1234", "22BH1234AA", "228H06418", "GJ05JB432",
    "GJ01", "GJ0", "GJ0I", "OADFIX2FR", "DFIX2F", "XX01AB1234", "", "MHO1DE2432",
    "W801086727", "GJ32K9819", "GJ01AB12O4", "6J01AB1234", "MH4702882", "22BH1234A",
]


_SWAP = {"O": "0", "0": "O", "I": "1", "1": "I", "S": "5", "5": "S", "B": "8", "8": "B",
         "Z": "2", "2": "Z", "G": "6", "6": "G", "Q": "0"}


def _corpus() -> list[str]:
    """Plate-shaped strings with OCR confusions, truncations and junk, so
    every branch (full as read, full by coercion, partial, rejected) runs."""
    rng = random.Random(25_09_2026)
    letters, digits = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0123456789"
    states = sorted(plates.STATE_CODES)
    out = list(FIXED)
    for _ in range(4000):
        if rng.random() < 0.8:
            p = (rng.choice(states) + "".join(rng.choices(digits, k=2))
                 + "".join(rng.choices(letters, k=rng.randint(1, 3)))
                 + "".join(rng.choices(digits, k=4)))
        else:
            p = ("".join(rng.choices(digits, k=2)) + "BH" + "".join(rng.choices(digits, k=4))
                 + "".join(rng.choices(letters, k=rng.randint(1, 2))))
        p = "".join(_SWAP.get(c, c) if rng.random() < 0.2 else c for c in p)
        if rng.random() < 0.3:
            p = p[: rng.randint(0, len(p))]
        if rng.random() < 0.1:
            p = p + rng.choice(letters + digits)
        out.append(p)
    return out


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_js_preview_grammar_matches_the_python_module() -> None:
    cases = _corpus()
    script = (
        f"import * as p from {json.dumps(JS.as_uri())};\n"
        "let data = '';\n"
        "process.stdin.on('data', (c) => (data += c));\n"
        "process.stdin.on('end', () => {\n"
        "  const out = JSON.parse(data).map((s) => [p.normalise(s), p.canonical(s),"
        " p.plateLike(s), p.coerce(s)]);\n"
        "  process.stdout.write(JSON.stringify(out));\n"
        "});\n"
    )
    r = subprocess.run(["node", "--input-type=module", "-e", script],
                       input=json.dumps(cases), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    mismatches = [
        (s, js, py)
        for s, js in zip(cases, got)
        if js != (py := [plates.normalise(s), plates.canonical(s),
                         plates.plate_like(s), plates.coerce(s)])
    ]
    assert not mismatches, mismatches[:10]
