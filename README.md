# Sentinel — Integrated Video Management & Analytics Platform

Entry to the [Gujarat Police Innovation Challenge 2026](https://sentinel.gujarat.gov.in/) (Home Department / SCRB). One platform over the departments' CCTV systems: a camera registry with a GIS view, continuous ANPR and analytics on live feeds, a watchlist with real-time alerts, and — the scored test — a vehicle's complete, timestamped, location-wise route from a single registration number.

**Status (20 Sep 2026): fresh, structured rebuild — documentation complete, code not yet started.** The previous build (`D:\projects\Sentinel_Repo`, submitted 15 Sep) works as a demo and is kept as read-only reference; everything it learned is carried over in `docs/`. Deadline: 28 Sep 2026.

## Start here

1. `CLAUDE.md` — the rules, the layout, how to work.
2. `docs/brief.md` — what must be delivered and how it is scored.
3. `docs/sandbox-findings.md` — what the sandbox and this laptop actually do (measured).
4. `docs/tasks.md` — the checklist; the plan is written there next.

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
  tasks.md                the checklist
  progress.md             session handoff, measurements, log
  demo-script.md          run sheet for both videos (verbatim)
  submission-checklist.md definition of done (verbatim)
  reference/              design record; old-build/ = the previous repo's docs, verbatim
deliverables/             HLD, deck, diagram, API doc, reports — as submitted, to be corrected
data/                     catalogue, laptop probe results, disclosed camera seed
backend/ frontend/ ml/    the three layers (each has its own CLAUDE.md)
```

## First commands (not yet run)

```bat
cd D:\projects\sentinel-gujarat
git init -b main
git add -A
git check-ignore .env data\logs models
git commit -m "Docs: fresh structured repo from the 15 Sep build"
git tag -a docs-v0 -m "Documentation baseline, 20 Sep 2026"
copy ..\Sentinel_Repo\.env .env
```

Never commit `.env`. Licence: Apache-2.0 (`LICENSE`).
