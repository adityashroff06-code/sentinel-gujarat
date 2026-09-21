# CLAUDE.md — Project Constitution (fresh build)

You are building **Sentinel**, Adi's entry to the Gujarat Police Innovation Challenge 2026 — an Integrated Video Management & Analytics Platform over the organisers' sandbox camera grid.
Read this file completely before any action. It outranks your instincts.

This repo is a **fresh, structured rebuild** started 20 September 2026. The previous build (`D:\projects\Sentinel_Repo`, submitted 15 Sep) works as a demo and is kept **read-only as a reference**; this repo reuses its knowledge, not its code. Everything that build learned is in `docs/` — read it before designing anything, because most of the surprises in this project have already been paid for once.

---

## 1. Situation

- **Deadline: 28 September 2026** (per Adi, 20 Sep — the original dates were 15 Sep submission and 22–23 Sep finale; confirm on the portal exactly which milestone the 28th is). **Build window: Mon 21 – Thu 24 Sep for the application, Fri 25 for the deliverables (GATE D at 09:00), Sat 26 soak and rehearsal, Sun 27 submit; Mon 28 is buffer** (`docs/tasks.md` calendar, decision F22). Nothing built in the final 48 hours before an evaluation gets demoed.
- Solo developer (Adi), one machine, work done in Claude Code sessions of one task each (`docs/tasks.md`, "How a session runs"). No team to parallelise across.
- **Hardware ceiling:** Windows 10/11 · Ryzen 5 3550H (4c/8t) · **8 GB RAM** · **GTX 1650, 4 GB VRAM** · 477 GB SSD. Python 3.13.9 (Anaconda, `D:\Anaconda\python.exe`); a portable ffmpeg already exists at `D:\projects\Sentinel_Repo\tools\ffmpeg\`.
- The organisers grade a **working system**, not a prototype. Their words: *"Mock-ups, animations, simulated interfaces, or concept videos without an operational backend will not be considered."*

**Consequence:** every design choice is made against a 4 GB VRAM / 8 GB RAM budget and a four-day clock. When a "proper" solution and a "fits the budget" solution conflict, take the second and document the first in the HLD.

---

## 2. The one thing that must work

*(verbatim from the previous build's constitution — unchanged because the test is unchanged)*

On evaluation day a **vehicle registration number is handed over live**. The system must return that vehicle's **complete, timestamped, location-wise route** across the camera network.

Everything else is supporting cast. If you are ever unsure what to work on, work on whatever makes that sentence true.

---

## 3. Absolute rules — never violate

*(verbatim from the previous build's constitution. These are MUST rules; they were all implemented and held.)*

1. **Credentials come from environment variables only.** Never hard-code, never commit, never print unmasked, never write into a log, a JSON file, or a database row. Any URL containing a password must be masked before it is displayed or stored. `.env` is gitignored; only `.env.example` is committed.
2. **One stream pull per camera.** The organisers state each connected client receives its own copy of the stream. Two pulls on one camera is a bug, not a preference. Fan out internally.
3. **All timing from PTS**, never from frame arrival time, never from `CAP_PROP_FPS`. On connect the gateway replays a buffered GOP, so early frames arrive faster than real time. Anything timed by arrival will compute impossible speeds.
4. **RTSP over TCP always** (`rtsp_transport=tcp`). If port 8554 is unreachable, fall back to HLS — do not fall back to UDP.
5. **Decoder warnings on join are never fatal.** `Could not find ref with POC`, `Error constructing the frame RPS`, `co located POCs unavailable` are expected. Log them, continue. A pipeline that exits on first decoder error will bounce forever.
6. **Never publish to the gateway, never call its control API, never attempt to download footage.** Consume only.
7. **Reconnect with jittered exponential backoff** — base 2 s, cap 30 s, multiplied by `random(0.5, 1.5)`. Never a tight retry loop.
8. **Never invent a measurement.** If a number is not produced by code that ran, label it an estimate. The HLD must distinguish measured from modelled.

Two rules added for the fresh build, from the previous build's post-mortem (`docs/decisions.md`):

9. **One time base.** Every stored timestamp carries which clock produced it and every row carries its provenance (`live | harvest | demo | test`). Never mix clocks in one route, never let a demo or test row pass as a live read.
10. **Everything runs under version control with a test for every bug fixed.** Commit after every completed task; a working commit is a fallback demo.

---

## 4. Architecture invariants

*(verbatim from the previous build's constitution; the design is carried over unchanged — `docs/architecture.md`)*

The architecture is **locked**: Model 1 (mandatory registry + GIS) + Model 2 (unified viewing & metadata analytics) + Pipeline 3 (event-triggered evidence capture), submitted as a Hybrid. Do not redesign it.

- The **registry is the single source of truth** for which cameras exist and how to reach them. Nothing hard-codes a camera id or a URL. Everything reads the registry, which is populated from the catalogue.
- **Watchlist matching happens locally**, against a cached list. Never a per-detection round trip to an external system.
- **Detections are written to durable storage before any alerting logic runs.** A detection must never exist only in the memory of the process about to crash.
- **Pipeline 1 stores nothing.** Live view is relay only.

---

## 5. Where things are

| Path | What it is |
|---|---|
| `docs/brief.md` | Why — the problem, the scored test, users, requirements, deliverables, evaluation. **Read first.** |
| `docs/constraints.md` | Hardware budget, licensing traps, sandbox rules (MUST, verbatim) |
| `docs/feed-rules.md` | The organisers' feed contract in executable form (MUST, verbatim) |
| `docs/sandbox-findings.md` | What the sandbox and this laptop actually do — measured, not assumed |
| `docs/architecture.md` | The locked target design, and what the sandbox forces on it |
| `docs/api.md` | The data contracts and API surface (binding), with the corrections learned |
| `docs/decisions.md` | Every choice carried over or still open, and why |
| `docs/tasks.md` | **The plan and the checklist**: one session per task, with the protocol every session follows (start → work → finish + write-off). Execute in order |
| `docs/progress.md` | Session handoff: current state, measurements, log |
| `docs/demo-script.md`, `docs/submission-checklist.md` | Run sheets for the videos and the submission (verbatim) |
| `docs/reference/` | The design record: hackathon scrape, sandbox spec, 80k review, Model 2/2.1 specs, glossary |
| `docs/reference/old-build/` | The previous build's own docs, verbatim — its `STATUS.md` is the findings log, its `P7-enhancements.md` the defect register, its `CONSTITUTION.md` the old `CLAUDE.md` (renamed so Claude Code never loads it as instructions: it says "today is 13 September" and forbids real authentication — **this file outranks it everywhere**) |
| `.claude/settings.json` | Claude Code permissions for every session (decision F38): the old repo is readable without prompting and never editable; `.env` is never readable or creatable by a session (Adi owns it); Bash timeouts raised to 5 min / 60 min for the soaks |
| `deliverables/` | The documents as submitted on 15 Sep (HLD, deck, diagram, API doc, reports) — the base for the revised submission |
| `data/` | The raw catalogue, the laptop probe results and the committed camera seed (department, coordinates, tier — disclosed) |
| `backend/`, `frontend/`, `ml/` | The three layers of the fresh build; each has its own `CLAUDE.md` with layer rules and package layout (decision F12) |
| `tests/`, `scripts/`, `CHECKSUMS.txt` | Pytest suite (`pytest.ini` at the root); one-off helpers (`doctor.py`, `replay_publish.py`, `smoke_frontend.py`); SHA-256 of every downloaded binary |
| `D:\projects\Sentinel_Repo\src`, `\ui`, `\launch.py` | The previous build's code. Read-only reference; consult when a doc cites a module |

---

## 6. How to work

1. Workflow is **discuss → plan → execute → review → test**, in that order. The plan lives in `docs/tasks.md`; every session follows its **"How a session runs"** protocol: read `docs/progress.md` → Current state, do one task, run its acceptance check, write the progress block, tick the task, commit. A task's *Read first* line is authoritative for what that session reads; the reading advice elsewhere in these docs yields to it. Do not start a phase before its predecessor's exit criteria are met.
2. Each task states its acceptance check. **A task is not done until its acceptance check has actually been run and passed** — not until the code looks right.
3. After each task, append a block to `docs/progress.md`: task id, status, what was actually observed, anything that surprised you. Record observations, not intentions.
4. Commit after every completed task. One fix, one test, one commit.
5. If a task's acceptance check fails twice, stop and write the blocker into `docs/progress.md` rather than improvising an alternative architecture.
6. **Respect the gates** in `docs/tasks.md`. A gate that fails triggers the stated cut. Do not negotiate with a gate.
7. Update `docs/api.md` in the same commit as any change to a stored shape or an endpoint. Update `docs/decisions.md` when a choice is made.

---

## 7. Code conventions

*(verbatim from the previous build's constitution, with one line superseded: the laptop runs **Python 3.13.9** and every dependency ships a cp313 wheel (validated 14 Sep), so read "Python 3.11" as "Python 3.13".)*

- **Python 3.11**, standard library first. Every dependency must justify its RAM.
- **One responsibility per module.** `frame_source.py` gets frames; it does not detect, log to the DB, or draw.
- **No silent failure.** Every `except` either handles meaningfully or re-raises. Never a bare `except: pass`.
- **Every long-running loop is interruptible** and closes its captures on exit. Leaked captures cost the department bandwidth and cost you VRAM.
- **Structured logging** (`logging`, not `print`) everywhere except CLI tools whose output is the product.
- **Type hints on every public function.** Docstring stating what it returns and what it raises.
- **All timestamps are timezone-aware UTC** in storage, converted only at the display layer. Naive datetimes are a bug.
- **Config lives in `config.py`**, read from environment with documented defaults. No magic constants scattered through modules.
- **The data contracts in `docs/03-data-contracts.md` are binding.** Do not add, rename, or retype a field without updating that document in the same commit.

For the fresh build the binding contract file is `docs/api.md`. Every process writes a rotating log file under `data/logs/`. Dependencies are pinned to exact versions. Downloaded binaries and model weights are checksum-verified against the root `CHECKSUMS.txt`. ffmpeg/ffprobe are called only through `backend.core.config.ffmpeg()`/`ffprobe()`.

---

## 8. Things that will waste your time — do not do them

- Do not introduce Postgres, Kafka, Docker, or Kubernetes into the demo. They are the production shape described in the HLD; on 8 GB of RAM they cost more than they return. SQLite and in-process queues for the demo.
- Do not train or fine-tune a model. Everything is inference on pre-trained weights.
- Do not use Ultralytics YOLO (AGPL-3.0 — a procurement blocker for a system the State would own), Elasticsearch or Redis. Licensing rules in `docs/constraints.md`.
- Do not copy ByteTrack's `kalman_filter.py` or use `open-image-models` YOLOv9 plate weights — GPL lineage in a state-owned stack (`docs/decisions.md`).
- Do not refactor working code for elegance. There is no time and no second reviewer.
- Do not write tests for their own sake. Write the acceptance check each task names, and a regression test for each bug fixed — nothing more.
- Do not demo anything built in the final 48 hours before an evaluation.
- Do not bulk-download the sandbox footage. Rule 6 forbids it and so do the organisers; test replay uses your own footage (`docs/decisions.md`).

---

## 9. When blocked

State the blocker plainly in `docs/progress.md` and move to the next task that does not depend on it. Do not stall the whole build on one camera, one plate, or one library. Partial coverage that works beats full coverage that does not.
