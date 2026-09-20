# PLAN — phase map, gates, cut lines

**Now:** 13 September 2026 · **Submission closes:** 15 September 2026 · **Usable time:** ~2 days.

Read `CLAUDE.md` first. Execute phases in order. Do not start a phase before its predecessor's exit criteria are met.

---

## Phase map

| Phase | Name | Budget | Exit criteria |
|---|---|---|---|
| **P0** | Bootstrap & probe | 1 h | Catalogue fetched, transport decided, registry populated, two measurements recorded |
| **P1** | Registry + API + GIS + live wall | 4 h | Every camera on a map, live video plays in the browser, gap-analysis report generates |
| **P2** | ANPR pipeline | 5 h | Sightings accumulating from ≥6 cameras, searchable, with plate crops |
| **P3** | Watchlist + real-time alerts | 2 h | A seeded plate passing a camera fires an alert on the dashboard within seconds |
| **P4** | **Route reconstruction** | 3 h | **A plate typed in returns a timestamped, location-wise route drawn on the map** |
| **P5** | Bonus analytics | 2 h | Object + intrusion detection surfaced in UI and reports |
| **P6** | Submission artefacts | 5 h | Both videos, HLD, deck, reports, links — all complete |

Totals ~22 h. That is deliberately more than two comfortable days, which is why the cut lines below exist.

---

## Gates — these are not negotiable

### GATE A — end of P0
**Question:** is any transport working, and how many cameras are live?
- If **zero** cameras reachable: stop building, contact the organisers, and record it in STATUS.md. Nothing downstream is possible.
- If **RTSP blocked, HLS working**: proceed HLS-only. Record it. Drop WHEP from the demo and say so in the HLD rather than pretending.
- If the catalogue carries **no department or coordinates**: create `data/camera_seed.csv` immediately and assign them once, explicitly, and disclose it in the submission.

### GATE B — end of P2
**Question:** is ANPR producing usable reads on real sandbox footage?
- If plate reads are accumulating with sane confidence → continue to P3/P4 as planned.
- If OCR is producing garbage: **do not spend the remaining time tuning the model.** Reduce to a smaller set of the best-quality cameras, accept lower recall, and continue. A route built from 4 good cameras scores; a perfect ANPR that never got integrated scores nothing.

### GATE C — the decisive one
**Question:** by the end of P4, can a plate typed into the UI return a timestamped route across ≥3 cameras?
- **Pass** → P5 and, only if time genuinely remains, Pipeline 3.
- **Fail** → **cut P5 and Pipeline 3 entirely, without debate.** Everything remaining goes to P4 and then P6. This is the scored moment; nothing else substitutes for it.

### GATE D — hard stop
**P6 must begin no later than the morning of 15 September regardless of code state.** An incomplete platform with complete documentation is submittable. A complete platform with no deck, no HLD and no videos scores on one of seven evaluation areas.

---

## Cut order — when time runs short, cut in exactly this sequence

1. Pipeline 3 evidence capture (already designed and validated — describe it, don't build it)
2. Intrusion detection (P5)
3. WHEP low-latency view (HLS covers it)
4. Object detection surfacing (P5)
5. Bulk CSV import UI (keep the API endpoint, drop the screen)
6. Fuzzy plate matching (keep exact matching only)

**Never cut:** the registry, the GIS map, the live wall, ANPR, sightings search, the watchlist, alerts, route reconstruction, or any P6 document.

---

## Standing instructions

- Update `STATUS.md` after every task, with what was **observed**, not what was intended.
- Two numbers must come from real runs and be carried into the HLD as measurements: sustained fps per camera under load, and real detection rate per camera. Everything else in the scaling section is labelled a model.
- Take a screen recording of anything that works the first time it works. Feeds go down; your footage of it working does not.
- Commit after every completed task. A working commit is a fallback demo.
