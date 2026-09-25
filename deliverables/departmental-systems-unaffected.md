# Departmental systems unaffected

**Sentinel: Model 2 deliverable (Unified Viewing & Metadata Analytics).** Gujarat Police Innovation Challenge 2026, 25 September 2026.
Sources: `deliverables/HLD.md` §2.6 (the guarantee to departments), §2.7 (two systems in one viewer), §3.3 (relayed, not recorded); `docs/architecture.md` Part A invariants, B2 and Part D.

**The guarantee.** Sentinel is consume-only. It pulls each camera's stream **read-only and once**, and fans it out inside the platform. It never publishes to a gateway, never calls a control API, never downloads stored footage and never writes to a departmental system. A department's cameras, VMS, storage and retention policy are exactly as they were before onboarding. The demonstrated system holds to this against the organisers' sandbox, and the source can be checked.

| On the department's side | Sentinel | Enforced in |
|---|---|---|
| Read the live stream | **Yes, read-only**: RTSP over TCP, HLS where RTSP is blocked, never UDP | `ml/ingest/rtsp.py` |
| A second connection to the same camera | **No.** The analytics decoder stream-copies a local 20-second window as it reads; the Live Wall plays that window | `backend/app/routes_hls.py` |
| Publish or write to a camera, gateway or VMS | **No.** Sentinel publishes only to its own mediamtx on `127.0.0.1` (the stock sample feeds) | `scripts/replay_publish.py` |
| Call a control API (PTZ, recording, configuration) | **No** | root rule 6 |
| Download or bulk-copy stored footage | **No.** The harvest of the organisers' recordings was cut | HLD Appendix B |
| Store video | Only on Sentinel's own disk: a **self-overwriting 20-second relay window** per analysed camera | HLD §1.4 |
| Hold the department's credentials | Environment variables only; never in the database, a URL, a response or an unmasked log line | root rule 1 |

**How each camera is viewed: two different systems in one viewer.**

| Camera | The Live Wall plays | Connection to the department's side |
|---|---|---|
| Sandbox camera analysed by the node (five, e.g. cam06) | the node's own pull, from its 20-second window | the single analytics pull, nothing more |
| Sandbox camera not analysed (the other 25) | **the organisers' own CDN recording**, relayed segment by segment at the current position on the shared timeline; the tile reads "CDN RECORDING" | none to the live gateway; one CDN request per segment however many people watch (in-memory cache, nothing on disk) |
| Local sample feed (`local01`–`local28`, stock footage) | Sentinel's own mediamtx HLS on `127.0.0.1` | none: Sentinel's own server |

**Why the other 25 show the CDN recording.** The five analysed cameras already hold five RTSP sessions on the gateway, which appears to allow about six per account (suspected from a run in which two of eight cameras pulled no frames; not measured). A live-wall RTSP pull would be a second connection and would starve the analytics. The organisers' own HLS copy, relayed once, keeps one pull per camera and leaves the gateway alone.

**What the relay fetches.** Only from the configured CDN origin, and only segment names listed in the playlist it has just fetched. It sits behind the login and is rate-limited. While the CDN refuses requests, a circuit breaker with jittered backoff answers the tile at once instead of retrying into a ban. The only upstream request that is not a `GET` is the CDN's viewer login, which obtains the session cookie a browser would hold.

**Health checks.** An analysed camera is never probed; its health is the freshness of its relay window. Other sandbox cameras get a short, paced RTSP `ffprobe` over TCP, two at a time, every five minutes. The CDN is never used as a probe.

**What a department provides.** A reachable stream endpoint (RTSP or ONVIF, or an HLS gateway) and a read-only account, registered as a URL template without the credential. Nothing is installed or changed on its VMS. A system reachable only through a vendor SDK, or with no inbound route, would be served by a department-side collector that dials out (Model 3, HLD §2.3; described, not built).

**Stated limits.** Sandbox departments and coordinates are seeded demonstration assignments. The 28 local feeds are stock footage at seeded coordinates (`sample-camera-dataset.csv`, first line). Pipeline 3 (evidence clips) is designed and validated separately and is not built, so no video is kept beyond the 20-second relay window.
