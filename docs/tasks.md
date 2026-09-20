# Tasks — the checklist

Execute in order. Each task states its acceptance check; a task is done when the check has **run and passed**, and its block is in `docs/progress.md`. Gates are not negotiable — a failed gate triggers its stated cut (`docs/decisions.md` C13).

Status: `[ ]` open · `[x]` done · `[-]` cut · `[!]` blocked (say why in progress.md)

---

## Phase 0 — Repo bootstrap (20 Sep)

- [x] **0.1** New repo written with structured docs; MUST content verbatim (`docs/progress.md` R0)
- [ ] **0.2** `git init -b main`, first commit, tag `docs-v0`. *Check:* `git check-ignore .env data/logs models` prints all three; `git grep -n -I -E "(rtsp|https?)://[^<{/ ]+:[^<{/ *]+@"` prints nothing; `git status` clean.
- [ ] **0.3** Confirm on the portal what the 28 Sep milestone is and the entry category; record in `docs/brief.md` §0 and `docs/decisions.md` O8.
- [ ] **0.4** Copy `.env` from the old repo (never commit it); reuse `D:\projects\Sentinel_Repo\tools\ffmpeg\...\bin` on PATH. *Check:* `ffmpeg -version` and `ffprobe -version` run from the new repo.
- [ ] **0.5** Record a rough screen capture of the **old** build running (dashboard, map, wall, route, alerts, reports) as insurance footage before anything else is touched.

## Phase 1 — The plan (20–21 Sep) — *written next, in this file*

Settle `docs/decisions.md` §5 (O1–O9), then write the phases below with one acceptance check per task, dated to fit 21–24 Sep with Thursday 24 Sep reserved for documents and videos. The previous build's phase files (`docs/reference/old-build/P0…P6-*.md`) contain reusable acceptance checks — e.g. P2.1's four frame-source checks, P3.2's cooldown check, P4.1's contract-shape check — copy them where they still apply.

- [ ] **1.1** Backend plan — storage + migrations, contract (`docs/api.md` Part B folded into Part A), auth + audit, registry/onboarding/import, sightings/route/watchlist/alerts/SSE, HLS relay, reports, health, stats, launcher, logs
- [ ] **1.2** ML plan — frame sources (RTSP pipe + tee, HLS VOD reader, local replay), time base, motion gate, detector (locked DirectML session), tracker, OCR (mobile models, consensus voting, budget), plate grammar, sightings, matcher, zones/object events, supervisor + watchdog + stats
- [ ] **1.3** Frontend plan — Command, Map, Live Wall, Search, Route, Alerts, **Watchlist**, **Cameras (add form + CSV import + edit)**, Zones, Reports; IST times; visible errors; API key handling
- [ ] **1.4** Test + replay plan — pytest layout; regression tests named per defect; local replay of own footage (RTSP + HLS); the 10-minute measurement run (O9)
- [ ] **1.5** Deliverables plan — HLD corrections (`docs/architecture.md` Part C), deck screenshots + rebuild, diagram PNG, `registry-api.json` re-export, reports regenerated with provenance, demo video 1 (own feed) and 2 (government feed), submission checklist walk-through from a private window
- [ ] **1.6** Gates — define GATE B (ANPR viability), GATE C (route across ≥3 cameras) and GATE D (documents start no later than 24 Sep morning) with their cuts

## Phases 2+ — to be written by Phase 1

*(backend · ML · frontend · integration · measurements · deliverables · soak + rehearsal)*

---

## Definition of done — the submission

Every box in `docs/submission-checklist.md` ticked against an observation, not an intention, and every link opened from a private window. The four deliverables (`docs/brief.md` §7), the ten dimensions, the Model 1 and Model 2 deliverables, the scalability section and the official feed-compliance checklist are all on that list.
