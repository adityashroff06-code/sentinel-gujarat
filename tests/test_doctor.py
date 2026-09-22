"""scripts/doctor.py — the environment doctor (task S0.4).

The doctor is stdlib-only and must run before the venv exists, so it is
imported here by path rather than as a package.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_doctor():
    spec = importlib.util.spec_from_file_location(
        "sentinel_doctor", REPO_ROOT / "scripts" / "doctor.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


doctor = _load_doctor()


@pytest.mark.skipif(os.name != "nt", reason="PATHEXT launch behaviour is Windows-only")
def test_npm_is_not_reported_missing_when_it_is_installed():
    """Regression: run_first_line passed a bare 'npm' to CreateProcess, which
    does no PATHEXT lookup, so an installed npm (shipped as npm.cmd beside an
    extensionless shell script) was printed as 'not found' — a false negative
    on a dependency S3.2's frontend scaffold needs. 23 Sep 2026."""
    import shutil

    if shutil.which("npm") is None:
        pytest.skip("npm genuinely absent on this machine")
    assert doctor.run_first_line(["npm", "--version"]) is not None


def test_run_first_line_returns_none_for_an_absent_program():
    assert doctor.run_first_line(["sentinel-no-such-program-xyz", "--version"]) is None


def test_run_first_line_finds_a_program_on_path():
    line = doctor.run_first_line([sys.executable, "--version"])
    assert line is not None and line.startswith("Python")


def test_env_var_names_returns_names_never_values(tmp_path):
    """Rule 1: the doctor prints variable NAMES only."""
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# a comment\n"
        "\n"
        "SENTINEL_EMAIL=someone@example.com\n"
        "export SENTINEL_PASSWORD=hunter2\n"
        "MALFORMED_LINE_NO_EQUALS\n",
        encoding="utf-8",
    )
    names = doctor.env_var_names(dotenv)
    assert names == ["SENTINEL_EMAIL", "SENTINEL_PASSWORD"]
    assert not any("example.com" in n or "hunter2" in n for n in names)


def test_doctor_output_is_ascii_so_the_windows_console_can_print_it():
    """Regression: em dashes in the header and the .env line rendered as
    replacement characters on the laptop's cp1252 console, corrupting the
    output the S0.4 write-off pastes into docs/progress.md. 23 Sep 2026."""
    source = (REPO_ROOT / "scripts" / "doctor.py").read_text(encoding="utf-8")
    assert "—" not in source
