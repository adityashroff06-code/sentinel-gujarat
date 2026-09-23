> **Editor's note (fresh build):** copied verbatim from the previous build's `06-submission-checklist.md`. Read `plan/P6-submission.md` as `docs/reference/old-build/P6-submission.md`, `docs/04-feed-rules.md` as `docs/feed-rules.md`, and "before 15 September" as the deadline in `docs/brief.md` §0. Ticked in task S5.5.

# 06 — Submission checklist

Tick against an observation, never an intention.

## Four required deliverables

- [ ] **Solution presentation** (PPT/PDF) — model + justification, overview, architecture, analytics approach, watchlist correlation methodology, technologies, scalability/interoperability/security, operational benefits
- [ ] **Technical proposal (HLD)** — all eight required elements, see `plan/P6-submission.md` §6.3
- [ ] **Demo video on own feed** — max 2–3 min: onboarding, AI detection, watchlist correlation, automatic alert
- [ ] **Live demo on Government feed** — onboarding, viewing, analytics output, **plus timestamped detection report**

## The ten dimensions

- [ ] Overall Architecture
- [ ] Integration Strategy
- [ ] AI & Video Analytics
- [ ] Cybersecurity Architecture
- [ ] Deployment Architecture
- [ ] Infrastructure Sizing
- [ ] Cost-Benefit Analysis
- [ ] Department-wise Information Requirements
- [ ] Scalability Strategy
- [ ] Future Roadmap

## Model 1 deliverables (mandatory model)

- [ ] Working registry portal with GIS map view
- [ ] Bulk + manual onboarding demonstrated
- [ ] Sample onboarded camera-metadata dataset
- [ ] Registry API documentation (`deliverables/registry-api.json`)
- [ ] Sample gap-analysis report

## Model 2 deliverables

- [ ] Unified viewer connected to feeds from **at least two different systems**
- [ ] ANPR demonstration on live or recorded feeds
- [ ] Searchable metadata dashboard
- [ ] **Architecture note proving departmental systems remain unaffected**

## Scalability section (~80,000 cameras)

- [ ] Central, regional and edge compute requirements
- [ ] GPU / accelerator requirements — **with the NVDEC decode ceiling named**
- [ ] Expected network bandwidth and low-bandwidth strategies
- [ ] Hot / warm / cold storage assumptions based on retention periods
- [ ] Load balancing, horizontal scaling, monitoring, logging, health checks
- [ ] High availability, backup, disaster recovery, cybersecurity controls
- [ ] Estimated implementation and operational costs
- [ ] Phased statewide rollout plan

## Feed compliance (official pre-submission list)

- [ ] Every client forces RTSP over TCP
- [ ] No timing logic depends on `CAP_PROP_FPS` or arrival time
- [ ] Inter-frame gaps don't crash or stall the pipeline
- [ ] Reconnect with backoff implemented **and tested by restarting a feed**
- [ ] Decoder warnings on join logged, not fatal
- [ ] Camera list and properties read from the catalogue
- [ ] Mixed H.264/H.265 and mixed resolutions handled
- [ ] Behaviour sane across a scene discontinuity

## Before hitting submit

- [ ] Every link opened from a **private window** and confirmed working
- [ ] Videos unlisted (YouTube) or "anyone with the link — Viewer" (Drive/OneDrive)
- [ ] No credentials anywhere: not in the repo, not in history, not in a video frame, not in a screenshot
- [ ] Every document exported to PDF and opening cleanly
- [ ] Numbers labelled: measured vs modelled
- [ ] The 30-vs-50 camera discrepancy noted rather than quietly assumed
- [ ] Submitted **before** 28 September, not on it

## Hosted demo and credentials (added 22 Sep — decisions F41, F42)

- [ ] The hosted URL opens over HTTPS from **another network** (mobile data) in a private window
- [ ] The evaluator credentials sign in, and the account can do what it is meant to and nothing more
- [ ] The alert stream, a crop image and a live tile all work through the tunnel
- [ ] The URL survives a laptop reboot with no manual step
- [ ] The credentials are in the submission form only — never in the repo, a screenshot or a video frame
- [ ] `/docs` and every `/api/*` path refuse an unauthenticated request; the five security headers are present
- [ ] The evaluator's first screen says what to click, which plates to try, and which rows are demonstration data

## Demonstration content (added 22 Sep)

- [ ] Video 1 shows **onboarding our own camera**, then a **real** watchlist hit and a **real** multi-camera route from our own footage (S3.6); anything injected is visibly labelled
- [ ] Video 2 shows ANPR **plus** vehicle, person and intrusion or line-crossing output on the government feed (FAQ 31), then the exported report
- [ ] The detection report carries timestamps and a provenance column

## Architecture names and the demo (added 24 Sep — decision F54, `docs/architecture.md` Part D)

- [ ] The HLD, the deck and both narrations name the proposal **Model 1 + Model 2 + Pipeline 3 (hybrid)**, and use the brief's names: live view = **Pipeline 1**, live streams = **Model 2**, Model 3 = VMS federation (described only)
- [ ] Pipeline 3 is stated as **designed and validated separately, not built**, in HLD §1, its pipeline table and Appendix B — nowhere claimed as running
- [ ] Every row of `docs/architecture.md` Part D matches what the HLD says
- [ ] The own-footage cameras are disclosed as replayed footage filmed on a named date; cam06 is disclosed as a live pull from the organisers' gateway
