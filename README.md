# Sentinel — Integrated Video Management & Analytics Platform

Entry to the [Gujarat Police Innovation Challenge 2026](https://sentinel.gujarat.gov.in/) (Home Department / SCRB). One platform over the departments' CCTV systems: a camera registry with a GIS view, continuous ANPR and analytics on live feeds, a watchlist with real-time alerts, and — the scored test — a vehicle's complete, timestamped, location-wise route from a single registration number.

**Status: fresh, structured rebuild in progress — the live state and the next task are always in `docs/progress.md` → Current state.** The plan is v2.5 (24 Sep): a login with roles, a hosted URL for the judges if the tunnel trial passes, ground truth from our own footage, working modules ported from the previous build rather than retyped, and a demo of Model 1 + Model 2 + Pipeline 1 with Pipeline 3 described, not built (`docs/architecture.md` Part D). The previous build (`D:\projects\Sentinel_Repo`, submitted 15 Sep) works as a demo and is kept as read-only reference; everything it learned is carried over in `docs/`. Deadline: 28 Sep 2026.

## Architecture

![Sentinel workflow and integration diagram](deliverables/Sentinel-Workflow-Integration-Diagram.png)

One pull per camera feeds three pipelines over the Model 1 registry: Pipeline 1 relays live video (relayed, not recorded), Pipeline 2 runs ANPR and analytics at the node and stores text rows and plate crops, and Pipeline 3 (evidence clips on a watchlist match) is designed and validated separately, not built in the demo. Source: [`deliverables/Sentinel-Workflow-Integration-Diagram.svg`](deliverables/Sentinel-Workflow-Integration-Diagram.svg); the full design is `deliverables/HLD.md`.

## Start here

1. `CLAUDE.md` — the rules, the layout, how to work.
2. `docs/brief.md` — what must be delivered and how it is scored.
3. `docs/sandbox-findings.md` — what the sandbox and this laptop actually do (measured).
4. `docs/tasks.md` — the plan: one-session tasks in two lanes (laptop and cloud), with the protocol every Claude Code session follows.

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
