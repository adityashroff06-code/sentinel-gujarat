# P6 — Submission artefacts  (budget: 5 hours) — MANDATORY, NEVER SQUEEZED

**GATE D: begin no later than the morning of 15 September regardless of code state.**

Three of the seven evaluation areas are documentation. An incomplete platform with complete documentation is submittable; a complete platform with no deck, no HLD and no videos scores on one area out of seven.

---

## P6.1 — Demo video 1: own feed  (max 2–3 minutes)

Follow `docs/05-demo-script.md`. Must show: onboarding and processing of feeds · AI detection and analytics · correlation against the watchlist · automatic real-time alert generation and visualisation.

**Record several takes. Keep the best. Have a fallback recording of each component working in isolation** — feeds go down, and footage of it working does not.

---

## P6.2 — Demo video 2: Government-provided feed

Must show: onboarding the provided feeds · successful live/recorded viewing · video-analytics output on that feed. **Plus an output report showing detected vehicles/number plates with timestamps** — exported from P4.4, not described.

---

## P6.3 — Technical proposal (HLD)

Every item below is explicitly required. Draw heavily on `reference/claude_architecture-review-80k.md` and `reference/claude_model-2-1-architecture-spec.md`.

- [ ] Overall architecture with diagrams and component interactions
- [ ] Integrating heterogeneous cameras, NVRs and VMS into a unified platform — **this is where Model 3 federation belongs**: adapter-per-vendor, metadata exchange bus, event correlation, extensible connector framework, and the department-side collector for departments exposing neither RTSP nor ONVIF
- [ ] Ingesting and managing live streams from geographically dispersed locations
- [ ] Integrating live feeds with watchlist databases and correlating into real-time alerts — **edge-cached matching**, not per-detection round trips to VAHAN/eGujCop
- [ ] AI analytics: ANPR, **FRS (description mandatory even though unimplemented)**, object detection, person and vehicle tracking
- [ ] Alert generation and notification workflow — prioritisation, visualisation, user interaction
- [ ] Scalability, interoperability, security, performance at ~80,000 cameras
- [ ] Technical prerequisites, assumptions, and **information required from participating departments**

**Honesty posture, stated in the document itself:** here is what we measured, here is what we modelled, here is what we would measure next. Label every modelled number as modelled. A jury that finds an invented measurement discounts everything else; a team that names its own boundary reads as senior.

---

## P6.4 — The ten dimensions

Confirm each has a home, and tick it off:

| # | Dimension | Artefact |
|---|---|---|
| 1 | Overall Architecture | HLD §1, `docs/01-architecture.md` |
| 2 | Integration Strategy | HLD §2 — including Model 3 federation |
| 3 | AI & Video Analytics | HLD §3 |
| 4 | **Cybersecurity Architecture** | HLD §4 — RBAC, segmentation, encryption in transit/at rest, credential vaulting, audit, least privilege |
| 5 | Deployment Architecture | HLD §5 — edge/regional/central |
| 6 | Infrastructure Sizing | HLD §6 — the GPU and decode tables, with the NVDEC ceiling named |
| 7 | Cost-Benefit Analysis | HLD §7 — including per-camera licensing arithmetic and the cloud-egress trap |
| 8 | **Department-wise Information Requirements** | Structured questionnaire — what we need from each department to assess integration feasibility |
| 9 | Scalability Strategy | HLD §8 — edge-first, the 3,750× WAN reduction |
| 10 | Future Roadmap | HLD §9 — pilot district → multi-district → statewide |

---

## P6.5 — Solution presentation (PPT/PDF)

- [ ] Proposed model — **Hybrid (Models 1 + 2 + evidence capture), with justification**
- [ ] Solution overview, objectives, key innovations
- [ ] High-level architecture and end-to-end workflow
- [ ] AI video analytics approach
- [ ] Watchlist correlation and real-time alerting methodology
- [ ] Key technologies, frameworks, tools — **with the licensing rationale**
- [ ] Scalability, interoperability, security, deployment
- [ ] Expected operational benefits and impact on policing and public safety

**Three slides that do disproportionate work:**
1. **Edge vs centralised WAN load** — 240 Gbps against 2.1 Mbps. The single most persuasive number in the submission, and it simultaneously explains why we did not choose Model 4.
2. **Storage honesty** — ~2.2 GB/day against ~1,600 GB/day for the same operational capability.
3. **What we do not do, and why** — no arbitrary rewind, no federation demo without departmental VMSs to federate, no live FRS. A team that names its boundaries reads as senior; a team presenting no trade-offs reads as inexperienced.

---

## P6.6 — Remaining small gaps

| Gap | Closure | Effort |
|---|---|---|
| Architecture note: departmental systems unaffected | One page — read-only pull, no writes, no config changes, no control-API calls | 30 min |
| Viewer on ≥2 different systems | Add a second source — local webcam or an independent stream — and show both in one viewer | 30 min |
| FRS approach described | Approach plus privacy controls. Implementation optional; **description is not** | 30 min |
| Private CCTV support | Registry supports `ownership='private'` plus a view-only tier; note the consent model | 30 min |
| Analog camera support | Analog → DVR/encoder → RTSP. One diagram; the path is identical downstream | 15 min |
| Department questionnaire | Same artefact as Dimension 8 | 1 h |
| Future roadmap | Phased rollout | 30 min |

---

## P6.7 — Submit

- [ ] Videos uploaded — **unlisted YouTube**, or Drive/OneDrive set to "anyone with the link — Viewer"
- [ ] **Open every link from a private window.** A link that only works while logged in is a failed submission.
- [ ] Hosted platform URL with test credentials, if hosting
- [ ] Repository link, if sharing — **verify no `.env`, no credentials, no keys in history**
- [ ] Every document exported to PDF and opening cleanly
- [ ] Official pre-submission checklist in `docs/04-feed-rules.md` ticked against observations
- [ ] Submitted **before** the 15 September deadline, not on it

---

**Exit P6 when:** the submission is uploaded and every link verified from a logged-out browser.
