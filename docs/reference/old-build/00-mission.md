# 00 — Mission: what is actually being graded

## The live test case

After registration, teams get live feeds from geographically distributed cameras spanning five departments (Health, Police, GSRTC, Panchayat, Municipal Corporation). The task:

1. Onboard the cameras onto **one integrated platform**.
2. Enable centralised monitoring and AI-powered video analytics.
3. **On evaluation day, a vehicle registration number is handed over.** Identify, trace and present that vehicle's movement across the network — across camera locations and times.
4. Demonstrate continuous cross-referencing of feeds against a watchlist database with automated real-time alerts on match.

**Expected output:** identification and tracing of the designated vehicle; **complete route traversed with timestamped, location-wise movement history**; a working watchlist DB continuously cross-referencing with automated alerts; evidence of integration, analytics, interoperability and scalability.

## The seven evaluation areas

| # | Area | Where we earn it |
|---|---|---|
| 1 | Successful test case on the Government feed | P1 + P2 + P4, plus demo video 2 |
| 2 | Solution presentation (PPT/PDF) | P6 |
| 3 | Solution architecture (HLD, diagrams, feasibility, security) | P6, drawing on `reference/` |
| 4 | Working platform & demonstration | P1–P4, demo video 1 |
| 5 | Video analytics output — ANPR, vehicle/person detection, **intrusion detection, object detection**, timestamps, output reports | P2 + P5 |
| 6 | Scalability & PoC readiness (~80,000 cameras) | P6, grounded in P0/P2 measurements |
| 7 | Submission completeness | P6 |

**Three of seven areas are documentation.** Do not let the code eat all the time.

Evaluation Area 5 names **four** analytics, not one. An ANPR-only submission is scored against a rubric listing intrusion detection and object detection explicitly. Those are cheap once the detector runs — see P5.

## Bonus criteria (bonus never compensates for a failed mandatory item)

- Innovative hybrid/customised architecture with clear operational value
- **Advanced cross-camera vehicle movement tracking or multi-camera correlation**
- Additional reliable analytics beyond mandatory ANPR
- Strong edge processing, bandwidth optimisation, low-connectivity operation
- Enhanced cybersecurity, privacy protection, auditability, RBAC
- Operational dashboards, automated alerts, health monitoring, integration-ready APIs

## Deliverables due 15 September

1. **Solution presentation** (PPT/PDF) — model chosen with justification, architecture, analytics approach, watchlist correlation methodology, technologies, scalability/interoperability/security, operational benefits.
2. **Technical proposal (HLD)** — architecture diagrams, heterogeneous integration approach, dispersed-stream ingestion, watchlist correlation, AI approach (ANPR, FRS, object detection, person/vehicle tracking), alert workflow, statewide scaling to ~80,000 cameras, prerequisites and **information required from participating departments**.
3. **Demo video on own feed** — max 2–3 minutes: onboarding, AI detection, watchlist correlation, automatic alert.
4. **Live demo on Government-provided feed** — onboarding, viewing, analytics output, **plus an output report showing detected vehicles/number plates with timestamps**.

Submission by unlisted YouTube or Drive/OneDrive link set to "anyone with the link". Optionally a hosted URL with test credentials, and a source repository link.

## The ten dimensions every submission must cover

Overall Architecture · Integration Strategy · AI & Video Analytics · Cybersecurity Architecture · Deployment Architecture · Infrastructure Sizing · Cost-Benefit Analysis · Department-wise Information Requirements · Scalability Strategy · Future Roadmap.

P6 maps each to an artefact. None may be missing.

## Known discrepancy

The public problem statement references ~50 cameras; the post-login guide lists `cam01` … `cam30`. Build against the catalogue (`cameras.json`), which the organisers call the contract. Note the discrepancy in the submission rather than assuming either number.
