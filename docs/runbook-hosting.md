# Runbook — keeping the public URL up (S3.5, decisions F41/F42)

The screening committee opens `https://<machine>.<tailnet>.ts.net`. This runbook is how that URL stays alive on the laptop from go-live until 28 Sep (and through 12–13 Oct if shortlisted). The platform behind it is started by `python launch.py start` and hardened by S3.0 (login, security headers, rate limits); only port 8000 is ever published — mediamtx (8554) and Vite (5173) stay on `127.0.0.1` (root rule 11).

## 0. One-time go-live — [Adi], ~15 minutes

1. Install Tailscale, sign in, enable **MagicDNS** and **HTTPS certificates** (admin console → DNS).
2. ```
   tailscale funnel --bg 8000
   ```
3. Confirm from **mobile data** (not the home Wi-Fi), in a private window: the login page loads over HTTPS, the evaluator credentials sign in, a live tile plays, an alert arrives while the page is open (SSE through the tunnel), sign-out returns to the login.
4. Reboot the laptop; within two minutes of logging in, the URL must answer again with no manual step (the scheduled tasks below do this).
5. Record the URL in `docs/progress.md` (never the password — the evaluator password exists **only** in the submission form).

**Fallback** if Funnel misbehaves (decision F42): a Cloudflare **named** tunnel on a domain Adi owns — never a quick tunnel, never ngrok free (URL changes on restart).

## 1. Accounts

```
.venv\Scripts\python -m backend.tools.users add evaluator --role evaluator
.venv\Scripts\python -m backend.tools.users add adi --role admin
```

Both prompt for the password (never on the command line, never in a log). `users list` shows names and roles only. A forgotten password is `users passwd <name>` — it revokes open sessions.

## 2. Environment for public exposure

In `.env` (Adi edits; sessions never read it):

- `SENTINEL_PUBLIC_HOST=<machine>.<tailnet>.ts.net` — switches on TrustedHost for that name, the `Secure` cookie flag and HSTS (S3.0).

Then restart the API (`python launch.py stop` / `start`).

## 3. Windows settings that keep it alive — [Adi]

- **Power**: Settings → System → Power → never sleep on AC; lid close = do nothing (or run with the lid open).
- **Windows Update**: pause until **14 Oct 2026** (Settings → Windows Update → Pause). An overnight forced reboot is the most likely outage.
- **Task Scheduler** (`taskschd.msc`) — three tasks, each "Run only when user is logged on", trigger **At log on**, restart on failure every 1 minute up to 3 times:
  1. `Sentinel Tunnel` — `tailscale` `funnel --bg 8000` (Start in: anywhere).
  2. `Sentinel Platform` — `python` `launch.py start` (Start in: `D:\projects\sentinel-gujarat`). `start` is idempotent: it re-seeds, skips finished setup, restarts dead processes.
  3. `Sentinel Watchdog` (added by S6.1b) — the restart watchdog + nightly `scripts/backup_db.py` snapshot.
- Auto-logon after reboot (netplwiz) is Adi's call; without it the URL waits for a manual login after power loss.

## 4. Where everything is when it breaks

| Symptom | Look at | Likely fix |
|---|---|---|
| URL dead, laptop up | `tailscale funnel status`; `data\logs\api.launcher.log` | re-run the Funnel task; `python launch.py start` |
| Login page up, tiles black | `data\logs\worker.launcher.log`, `data\worker_stats.json` (stale `written_at` = worker down) | `python launch.py stop` then `start` |
| Sandbox cameras down (their side) | Command screen's feed-status strip says "feed down" per camera | nothing — the `local01..local04` sample feeds (F58) keep the platform demonstrable; say so on camera if recording |
| Everything slow / OCR lagging | `data\worker_stats.json` `fps_sustained`, `rss_mb` | reduce `SENTINEL_ACTIVE_CAMERAS` in `.env`, restart |
| DB suspect | `data\backup\` (nightly + pre-migration snapshots) | stop, copy the newest snapshot over `data\sentinel.db`, start |

Logs rotate under `data\logs\` (one file per process: `api`, `worker`, `supervisor`, `ingest.<cam>`, `mediamtx`, `replay_publish`, plus the two `*.launcher.log` streams). The stats snapshot `data\worker_stats.json` rewrites every 10 s while the worker lives — its `written_at` is the platform's heartbeat.

## 5. The daily check while hosted (until 28 Sep)

From a phone on mobile data, one minute: open the URL → sign in as evaluator → Command shows tiles + a recent read timestamp → sign out. If any step fails, table 4. Before the 27 Sep submission, S5.5's private-window walkthrough replaces this check.
