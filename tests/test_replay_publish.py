"""scripts/replay_publish.py — checksum discipline (task S2.2, decision F25):
the recorded SHA-256 is verified on every run and a tampered or unrecorded
binary is refused. Loaded by path, like scripts/doctor.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "replay_publish", REPO_ROOT / "scripts" / "replay_publish.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def rp(tmp_path, monkeypatch):
    module = _load()
    tools = tmp_path / "tools" / "mediamtx"
    tools.mkdir(parents=True)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "TOOLS_DIR", tools)
    monkeypatch.setattr(module, "CHECKSUMS", tmp_path / "CHECKSUMS.txt")
    return module


def test_verify_passes_a_recorded_zip_and_refuses_a_tampered_one(rp):
    zip_path = rp.TOOLS_DIR / "mediamtx_v1.0.0_windows_amd64.zip"
    zip_path.write_bytes(b"payload")
    rp.CHECKSUMS.write_text(
        "# comment line\n"
        f"{rp.sha256_file(zip_path)}  https://example/v1.0.0  "
        f"tools/mediamtx/{zip_path.name}\n",
        encoding="utf-8",
    )
    assert rp.verify_zip() == zip_path         # intact: passes

    zip_path.write_bytes(b"tampered!")
    with pytest.raises(SystemExit, match="mismatch"):
        rp.verify_zip()                        # altered: refused


def test_verify_demands_a_fetch_and_a_recorded_entry(rp):
    with pytest.raises(SystemExit, match="not fetched"):
        rp.verify_zip()                        # no zip at all

    zip_path = rp.TOOLS_DIR / "mediamtx_v1.0.0_windows_amd64.zip"
    zip_path.write_bytes(b"payload")
    with pytest.raises(SystemExit, match="no CHECKSUMS.txt entry"):
        rp.verify_zip()                        # zip present, never recorded


def test_publish_command_reencodes_by_default_and_copies_on_request(rp):
    default = rp._publish_cmd("clip.mp4", "local01", 8554)
    assert "libx264" in default and "-g" in default          # 2 s GOP forced
    assert default[-1] == "rtsp://127.0.0.1:8554/stream/local01"

    copied = rp._publish_cmd("clip.mp4", "local01", 8554, copy=True)
    i = copied.index("-c:v")
    assert copied[i + 1] == "copy" and "libx264" not in copied
    assert copied[-1] == "rtsp://127.0.0.1:8554/stream/local01"
