# Working on Sentinel (build sessions)

Moved here from the top of `README.md` in S5.5 (25 Sep 2026), when the README was rewritten for the judges. This is how the build itself is run; a judge does not need it.

## Start here

1. `CLAUDE.md` — the rules, the layout, how to work.
2. `docs/brief.md` — what must be delivered and how it is scored.
3. `docs/sandbox-findings.md` — what the sandbox and this laptop actually do (measured).
4. `docs/tasks.md` — the plan: one-session tasks in two lanes (laptop and cloud), with the protocol every Claude Code session follows.
5. `docs/progress.md` → **Current state** — the live state and the next task, always.

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
  demo-script.md          run sheet for both videos
  submission-checklist.md definition of done
  runbook-hosting.md      keeping the public URL up (S3.5)
  runbook-new-feeds.md    onboarding a fresh camera grid (S3.7)
  reference/              design record; old-build/ = the previous repo's docs, verbatim
deliverables/             HLD, deck, diagram, API doc, reports, sample dataset
data/                     catalogue, probe results, disclosed camera seed, local-feed register
backend/ frontend/ ml/    the three layers (each has its own CLAUDE.md)
scripts/ tests/           one-off helpers and the pytest suite (pytest.ini at the root)
```

## How a session runs

Every session follows the protocol at the top of `docs/tasks.md` — read `docs/progress.md` → Current state, do one task, run its acceptance check, write the progress block, tick the task, commit — so work resumes from "Current state" after any interruption. `.env` is Adi's: no Claude session reads or writes it (`.claude/settings.json` enforces it). Never commit `.env`.
