# 01 — Architecture (LOCKED — do not redesign)

Full background in `reference/claude_model-2-1-architecture-spec.md`. This file is the operative summary.

## One paragraph

One stream pull per camera feeds three concurrent pipelines. **Pipeline 1** relays live video to the control room and stores nothing. **Pipeline 2** runs AI analytics and stores only text metadata plus a small plate crop. **Pipeline 3** keeps a fixed-size rolling buffer of compressed video and promotes a ±30 s clip to permanent storage *only* when a watchlist match fires. Underneath all three sits the **Model 1 registry** — the mandatory camera inventory and GIS layer that tells every component which cameras exist, where they are, and how to reach them.

## Diagram

```
              ┌──────────────────────────────────────────┐
              │  MODEL 1 — CAMERA REGISTRY + GIS         │
              │  the control plane for everything below  │
              │  · id, department, location, geometry    │
              │  · stream URLs, codec, resolution        │
              │  · health, last_seen, fps_tier, ROI      │
              └────────────────┬─────────────────────────┘
                               │ tells workers what to connect to
                               ▼
CAMERA GRID ──── ONE pull per camera (HLS or RTSP/TCP) ────► INGEST WORKER
                                                                  │
        ┌─────────────────────────────────────────────────────────┼──────────────────────┐
        │                              │                                                 │
  PIPELINE 1                     PIPELINE 2                                        PIPELINE 3
  LIVE VIEW (relay)              AI ANALYTICS                                  EVIDENCE CAPTURE
        │                              │                                                 │
  hls.js in browser         sample @ fps_tier (PTS-driven)                ring buffer, HLS segments
  WHEP if reachable         motion gate → skip empty frames               fixed N, self-overwriting
  NOTHING SAVED             detect vehicle → crop → plate → OCR                          │
        │                   match vs LOCAL watchlist              ◄── promote(t±30s) on match only
        ▼                              │                                                 ▼
  CONTROL ROOM WALL          sighting row + plate crop (~2 KB)                 CLIP + SHA-256 + audit
  multi-camera grid                    │
                                       ▼
                          SEARCH + GIS ROUTE + ALERTS
                          "where has GJ01AB1234 been?"
```

## What is stored, and what is not

| Pipeline | Persists | Does not persist |
|---|---|---|
| 1 — Live view | nothing | all video passing through |
| 2 — Analytics | sighting rows (text) + plate crop (~2 KB) | frames, full-frame JPEGs |
| 3 — Evidence | promoted clip + audit row | the rolling buffer (self-overwriting) |

**The governing principle: watching is not the same as storing.** Video becomes permanent only where a specific, logged, auditable watchlist match justifies it. This is a civil-liberties position, not only an optimisation, and it maps onto the bonus criterion for privacy protection and auditability. State it in the deck.

## What we build vs what we describe

| | Built for the demo | Described in the HLD only |
|---|---|---|
| Registry + GIS | ✅ | scaling to 80,000 entries |
| Live viewing | ✅ | video-wall layouts at control-room scale |
| ANPR + sightings + search | ✅ | GPU fleet sizing, INT8, edge deployment |
| Watchlist + alerts | ✅ (local seed DB) | VAHAN / SARTHI / eGujCop / AFIS / NAFIS adapter design |
| Cross-camera route | ✅ | Re-ID at statewide scale |
| Object + intrusion detection | ✅ if P4 passes | — |
| Evidence clips (Pipeline 3) | only if time remains | the full design, already validated |
| **Model 3 federation layer** | ❌ not buildable | ✅ the path from sandbox to 26 heterogeneous departments |
| FRS | ❌ | approach + privacy controls (description is mandatory) |

## On Model 3

The sandbox exposes bare stream endpoints. There are no departmental VMS platforms in it to federate, so a Model 3 demo would be demonstrating something that is not there. Model 3 belongs in the HLD as the answer to **heterogeneity, not scale** — 26 departments running 26 different systems, which is true on day one of a real deployment rather than at some later camera count. It is the honest completion of the connector-sprawl weakness already documented as Model 2's structural flaw, with the department-side collector as the mitigation for departments exposing neither RTSP nor ONVIF.

Frame it that way in the deck. "We will federate later" reads as filler; "here is the weakness we named, and here is its structural fix" reads as engineering.

## Design invariants

1. One pull per camera. Fan out internally, never open a second connection to a source.
2. Watchlist matching is local, against a cached list.
3. All timing from PTS.
4. RTSP over TCP, or HLS. Never UDP.
5. Detections are persisted before any alerting logic runs.
6. The registry is the single source of truth, populated from the catalogue.
