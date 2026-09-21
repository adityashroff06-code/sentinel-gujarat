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
- [ ] Submitted **before** 15 September, not on it
