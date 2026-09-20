# CLAUDE.md — Project Constitution

You are building **Sentinel**, a submission for the Gujarat Police Innovation Challenge 2026.
Read this file completely before any action. It outranks your instincts.

---

## 1. Situation

- **Submission closes 15 September 2026.** Today is 13 September. You have ~2 working days.
- Solo developer (Adi). One machine. No team to parallelise across.
- **Hardware ceiling:** Windows 10/11 · Ryzen 5 3550H (4c/8t) · **8 GB RAM** · **GTX 1650, 4 GB VRAM** · 477 GB SSD.
- The organisers grade a **working system**, not a prototype. Their words: *"Mock-ups, animations, simulated interfaces, or concept videos without an operational backend will not be considered."*

**Consequence:** every design choice is made against a 4 GB VRAM / 8 GB RAM budget and a two-day clock. When a "proper" solution and a "fits the budget" solution conflict, take the second and document the first in the HLD.

---

## 2. The one thing that must work

On evaluation day a **vehicle registration number is handed over live**. The system must return that vehicle's **complete, timestamped, location-wise route** across the camera network.

Everything else is supporting cast. If you are ever unsure what to work on, work on whatever makes that sentence true.

---

## 3. Absolute rules — never violate

1. **Credentials come from environment variables only.** Never hard-code, never commit, never print unmasked, never write into a log, a JSON file, or a database row. Any URL containing a password must be masked before it is displayed or stored. `.env` is gitignored; only `.env.example` is committed.
2. **One stream pull per camera.** The organisers state each connected client receives its own copy of the stream. Two pulls on one camera is a bug, not a preference. Fan out internally.
3. **All timing from PTS**, never from frame arrival time, never from `CAP_PROP_FPS`. On connect the gateway replays a buffered GOP, so early frames arrive faster than real time. Anything timed by arrival will compute impossible speeds.
4. **RTSP over TCP always** (`rtsp_transport=tcp`). If port 8554 is unreachable, fall back to HLS — do not fall back to UDP.
5. **Decoder warnings on join are never fatal.** `Could not find ref with POC`, `Error constructing the frame RPS`, `co located POCs unavailable` are expected. Log them, continue. A pipeline that exits on first decoder error will bounce forever.
6. **Never publish to the gateway, never call its control API, never attempt to download footage.** Consume only.
7. **Reconnect with jittered exponential backoff** — base 2 s, cap 30 s, multiplied by `random(0.5, 1.5)`. Never a tight retry loop.
8. **Never invent a measurement.** If a number is not produced by code that ran, label it an estimate. The HLD must distinguish measured from modelled.

---

## 4. Architecture invariants

The architecture is **locked**: Model 1 (mandatory registry + GIS) + Model 2 (unified viewing & metadata analytics) + Pipeline 3 (event-triggered evidence capture), submitted as a Hybrid. Do not redesign it. Details in `docs/01-architecture.md`.

- The **registry is the single source of truth** for which cameras exist and how to reach them. Nothing hard-codes a camera id or a URL. Everything reads the registry, which is populated from the catalogue.
- **Watchlist matching happens locally**, against a cached list. Never a per-detection round trip to an external system.
- **Detections are written to durable storage before any alerting logic runs.** A detection must never exist only in the memory of the process about to crash.
- **Pipeline 1 stores nothing.** Live view is relay only.

---

## 5. How to work

1. Read `plan/PLAN.md` for the phase map, then the phase file for the task you are on.
2. Execute tasks **in the order given**. Each task states its acceptance check. **A task is not done until its acceptance check has actually been run and passed** — not until the code looks right.
3. After each task, append a line to `plan/STATUS.md`: task id, status, what was actually observed, anything that surprised you.
4. If a task's acceptance check fails twice, stop and write the blocker into `plan/STATUS.md` rather than improvising an alternative architecture.
5. **Respect the gates.** Gates are in `plan/PLAN.md`. A gate that fails triggers the stated cut. Do not negotiate with a gate.

---

## 6. Code conventions

- **Python 3.11**, standard library first. Every dependency must justify its RAM.
- **One responsibility per module.** `frame_source.py` gets frames; it does not detect, log to the DB, or draw.
- **No silent failure.** Every `except` either handles meaningfully or re-raises. Never a bare `except: pass`.
- **Every long-running loop is interruptible** and closes its captures on exit. Leaked captures cost the department bandwidth and cost you VRAM.
- **Structured logging** (`logging`, not `print`) everywhere except CLI tools whose output is the product.
- **Type hints on every public function.** Docstring stating what it returns and what it raises.
- **All timestamps are timezone-aware UTC** in storage, converted only at the display layer. Naive datetimes are a bug.
- **Config lives in `config.py`**, read from environment with documented defaults. No magic constants scattered through modules.
- **The data contracts in `docs/03-data-contracts.md` are binding.** Do not add, rename, or retype a field without updating that document in the same commit.

---

## 7. Things that will waste your remaining time — do not do them

- Do not introduce Postgres, Kafka, Docker, or Kubernetes into the demo. They are the production shape described in the HLD; on 8 GB of RAM they cost more than they return. SQLite and in-process queues for the demo.
- Do not train a model. Everything is inference on pre-trained weights.
- Do not build authentication beyond a single hard-coded demo role unless P1–P4 are complete.
- Do not refactor working code for elegance. There is no time and no second reviewer.
- Do not use Ultralytics YOLO (AGPL-3.0 — a procurement blocker for a system the State would own). Licensing rules in `docs/02-hard-constraints.md`.
- Do not write a test suite for its own sake. Write the acceptance check each task names, and nothing more.

---

## 8. When blocked

State the blocker plainly in `plan/STATUS.md` and move to the next task that does not depend on it. Do not stall the whole build on one camera, one plate, or one library. Partial coverage that works beats full coverage that does not.
