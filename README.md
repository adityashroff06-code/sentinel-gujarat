# Sentinel — Integrated Video Management & Analytics Platform

Entry to the [Gujarat Police Innovation Challenge 2026](https://sentinel.gujarat.gov.in/) (Home Department / SCRB). One platform over the departments' CCTV systems: a camera registry with a GIS view, continuous ANPR and analytics on live feeds, a watchlist with real-time alerts, and — the scored test — a vehicle's complete, timestamped, location-wise route from a single registration number.

**Status (22 Sep 2026): fresh, structured rebuild in progress — backend core, plate grammar, registry API with auth and audit, seed tools and the replay frame source are in and under test (S0.2–S2.1); the next task is S2.2.** The plan is v2.3, which adds a login with roles, a hosted URL for the judges, and ground truth from our own footage. The previous build (`D:\projects\Sentinel_Repo`, submitted 15 Sep) works as a demo and is kept as read-only reference; everything it learned is carried over in `docs/`. Deadline: 28 Sep 2026.

## Start here

1. `CLAUDE.md` — the rules, the layout, how to work.
2. `docs/brief.md` — what must be delivered and how it is scored.
3. `docs/sandbox-findings.md` — what the sandbox and this laptop actually do (measured).
4. `docs/tasks.md` — the plan: 30 one-session tasks with the protocol every Claude Code session follows.

## Layout

```
CLAUDE.md                 rules + pointers (read first)
docs/
  brief.md                why: problem, scored test, requirements, deliverables, evaluation
  constraints.md          hardware budget, licensing traps, sandbox rules (MUST, verbatim)
  feed-rules.md           the organisers' feed contract in executable form (MUST, verbatim)
  sandbox-findings.md     measured facts about the grid and this laptop
  architecture.md         the locked design + what the sandbox forces + claims to correct
  api.md                  data contracts and API surface (binding) + corrections learned
  decisions.md            choices carried over, made, and still open
  tasks.md                the plan and checklist (one task per Claude Code session)
  progress.md             session handoff, measurements, log
  demo-script.md          run sheet for both videos (verbatim)
  submission-checklist.md definition of done (verbatim)
  reference/              design record; old-build/ = the previous repo's docs, verbatim
deliverables/             HLD, deck, diagram, API doc, reports — as submitted, to be corrected
data/                     catalogue, laptop probe results, disclosed camera seed
backend/ frontend/ ml/    the three layers (each has its own CLAUDE.md)
```

## First commands

Run task **S0.2** from `docs/tasks.md` (the repo and its GitHub remote already exist — S0.2 commits the documentation baseline, tags `docs-v0` and pushes), then S0.3–S0.5, then the sessions in order. Before S0.4, Adi creates `.env` himself (task S0.4 says how); no Claude session reads or writes that file — `.claude/settings.json` enforces it. Every session follows the protocol at the top of `docs/tasks.md` and writes itself off in `docs/progress.md`, so work resumes from "Current state" after any interruption.

Never commit `.env`. Licence: Apache-2.0 (`LICENSE`).
