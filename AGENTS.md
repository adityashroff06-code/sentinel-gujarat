# Codex repository instructions

Read `CODEX.md` before reviewing or changing this repository. It defines Codex's review role, verification boundaries and handoff format.

Claude Code is the primary implementation agent and follows `CLAUDE.md`. Codex reviews by default; implement changes only when the user asks. Also read `CLAUDE.md` for shared project constraints, using the current root-level paths explained in `CODEX.md`.

Do not automatically execute the next plan task, modify Claude's in-progress work, update task completion marks, or commit changes during a review. The user's current request determines the scope.
