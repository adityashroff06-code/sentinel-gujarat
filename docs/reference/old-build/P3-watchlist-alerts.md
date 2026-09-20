# P3 — Watchlist + real-time alerts  (budget: 2 hours)

Named directly in the test case: *"demonstrate continuous cross-referencing of live feeds against a representative watchlist database with automated real-time alerts on match."* Our own watchlist is explicitly permitted.

---

## P3.1 — Seed the watchlist

**Do:** `src/tools/seed_watchlist.py`. Populate `watchlist` per `docs/03-data-contracts.md` §3 with:
- **5–10 plates actually observed in the feeds** during P2, so the demo produces genuine hits on real vehicles
- **20–30 invented plates** across all categories and severities, so the table looks like a real watchlist rather than a rigged one

Record in STATUS.md which entries came from observation. Being straight about this in the deck is a strength, not a weakness — the rules invite us to bring our own data.

**Acceptance:** the table is populated, and the UI lists it.

---

## P3.2 — Matcher

**Do:** `src/alerting/matcher.py`. On every committed sighting, match against the **locally cached** watchlist — never an external round trip, per the architecture invariant. Use `plate_match()` from `src/anpr/plates.py`: exact first, ambiguity-map second, Levenshtein ≤1 third. Record `match_type` and `match_distance` on the alert.

**Never alert on a partial read** (normalised length < 8). Store it as a sighting; do not fire.

**Cooldown:** the same plate on the same camera does not re-alert within 5 minutes. Without this, one vehicle in view produces an unusable alert stream and operators stop trusting it.

**Acceptance:** insert a synthetic sighting for a watchlisted plate → exactly one alert. Insert it four more times inside the cooldown → still one alert.

---

## P3.3 — Alert service and live push

**Do:** create the alert row, then broadcast over SSE at `GET /api/alerts/stream`. **Persist before broadcasting** — a detection must never exist only in the memory of the process about to crash. In the demo this is an in-process queue; the HLD describes Kafka/NATS as the production durable queue, and that distinction should be stated rather than blurred.

**Acceptance:** with the dashboard open, a matching sighting appears in the alert panel within ~2 seconds without a page refresh.

---

## P3.4 — Alert panel UI

**Do:** a live-updating panel, newest first, severity colour-coded. Each alert shows plate, **plate crop**, camera, department, timestamp, category, match type. Click → detail view with the camera's location on the map and a "view this vehicle's route" link into P4. Acknowledge button hitting `POST /api/alerts/{id}/ack`.

The crop matters more than it looks: it is the difference between an alert an operator trusts and an alert an operator ignores.

**Acceptance:** an alert fires live during a real run, is visible with its crop, and acknowledging it persists across a page reload.

---

**Exit P3 when:** a real vehicle whose plate is on the watchlist passes an active camera and an alert appears on the dashboard within seconds. **Record this.** It is demo video material and it may not repeat on command.
