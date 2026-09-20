// Sentinel: Solution Presentation (P6.5). Build: node build_deck.js
// Output: ../Sentinel-Solution-Presentation.pptx
const pptxgen = require("pptxgenjs");
const path = require("path");

const IMG = (f) => path.join(__dirname, "img", f);
const C = {
  bg: "0A0E14", panel: "111823", panel2: "16202E", border: "1E2A3A",
  text: "E6EDF5", muted: "8A97A6", accent: "3D7FD6", danger: "D64F6A",
  ok: "39A56A", amber: "E0912F", purple: "B45FD1", white: "FFFFFF",
};
const FONT = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "Adi";
pres.title = "Sentinel: Solution Presentation";

// ------------------------------------------------------------ helpers
function base(notes) {
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s.addText("SENTINEL  ·  Gujarat Police Innovation Challenge 2026", {
    x: 0.5, y: 7.02, w: 8, h: 0.3, fontFace: FONT, fontSize: 9,
    color: C.muted, isTextBox: true, margin: 0,
  });
  if (notes) s.addNotes(notes);
  return s;
}
function title(s, t, sub) {
  s.addText(t, { x: 0.5, y: 0.35, w: 12.3, h: 0.7, fontFace: FONT, fontSize: 30,
    bold: true, color: C.text, isTextBox: true, margin: 0 });
  if (sub) s.addText(sub, { x: 0.5, y: 1.02, w: 12.3, h: 0.4, fontFace: FONT,
    fontSize: 14, color: C.muted, isTextBox: true, margin: 0 });
}
function card(s, x, y, w, h) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: C.panel },
    line: { color: C.border, width: 0.75 }, rectRadius: 0.12 });
}
function bullets(s, items, x, y, w, h, size = 13) {
  const arr = items.map((t, i) => {
    const o = typeof t === "string" ? { text: t } : t;
    return { text: o.text, options: { bullet: true, breakLine: i < items.length - 1,
      color: o.color || C.text, bold: !!o.bold, paraSpaceAfter: 5 } };
  });
  s.addText(arr, { x, y, w, h, fontFace: FONT, fontSize: size, color: C.text,
    isTextBox: true, valign: "top", margin: 2 });
}
function label(s, t, x, y, w, size = 10, color = C.muted) {
  s.addText(t, { x, y, w, h: 0.3, fontFace: FONT, fontSize: size, color,
    isTextBox: true, margin: 0 });
}
function stat(s, num, lbl, x, y, w, color = C.text) {
  s.addText(num, { x, y, w, h: 0.9, fontFace: FONT, fontSize: 44, bold: true,
    color, isTextBox: true, margin: 0, align: "center" });
  s.addText(lbl, { x, y: y + 0.9, w, h: 0.5, fontFace: FONT, fontSize: 12,
    color: C.muted, isTextBox: true, margin: 0, align: "center" });
}
function shot(s, file, x, y, w, caption) {
  const h = w * 9 / 16;
  s.addImage({ path: IMG(file), x, y, w, h, rounding: false });
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.bg, transparency: 100 },
    line: { color: C.border, width: 0.75 } });
  if (caption) label(s, caption, x, y + h + 0.06, w, 9);
  return h;
}
function pill(s, t, x, y, color) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.15, h: 0.3, fill: { color },
    line: { color, width: 0 }, rectRadius: 0.15 });
  s.addText(t, { x, y, w: 1.15, h: 0.3, fontFace: FONT, fontSize: 10, bold: true,
    color: C.white, align: "center", valign: "middle", isTextBox: true, margin: 0 });
}
const NOTE_CAP = "UI capture: development render on a controlled test scenario. Replace with the live-demo capture.";

// ============================================================ 1. TITLE
{
  const s = base("Open with the sentence that is graded: a registration number handed over live returns that vehicle's complete timestamped route across the network.");
  s.addText("SENTINEL", { x: 0.7, y: 1.6, w: 12, h: 1.1, fontFace: FONT, fontSize: 60,
    bold: true, color: C.text, isTextBox: true, margin: 0, charSpacing: 6 });
  s.addText("Integrated Video Management and Analytics Platform", { x: 0.7, y: 2.7, w: 12,
    h: 0.6, fontFace: FONT, fontSize: 24, color: C.text, isTextBox: true, margin: 0 });
  s.addText("A hybrid of Reference Model 1 (Centralised CCTV Registry and GIS) and Model 2 (Unified Viewing and Metadata Analytics), plus event-triggered evidence capture. Model 3 federation is the documented integration path.",
    { x: 0.7, y: 3.35, w: 11.5, h: 0.8, fontFace: FONT, fontSize: 14, color: C.muted, isTextBox: true, margin: 0 });
  ["Police", "GSRTC", "Municipal", "Panchayat", "Health"].forEach((d, i) =>
    pill(s, d, 0.7 + i * 1.3, 4.5, [C.accent, C.amber, C.ok, C.purple, C.danger][i]));
  s.addText("One platform. Five departments. Watching is not storing.", { x: 0.7, y: 5.0, w: 12, h: 0.5,
    fontFace: FONT, fontSize: 16, italic: true, color: C.text, isTextBox: true, margin: 0 });
  s.addText("Gujarat Police Innovation Challenge 2026  ·  Home Department / SCRB  ·  Submission by Adi", {
    x: 0.7, y: 6.2, w: 12, h: 0.4, fontFace: FONT, fontSize: 12, color: C.muted, isTextBox: true, margin: 0 });
}

// ============================================================ 2. PROBLEM + TEST CASE
{
  const s = base("The problem is heterogeneity first and scale second. The test case is a single vehicle route.");
  title(s, "The problem, and what is actually graded");
  card(s, 0.5, 1.6, 6.0, 5.1);
  label(s, "TODAY", 0.75, 1.75, 5, 11, C.accent);
  bullets(s, [
    "26 government departments run independent, standalone CCTV systems",
    "Mixed analog and IP cameras, different vendors and VMS platforms, incompatible feed protocols",
    "Storage fragmented: cloud for some, local for others, retention from 7 days to over 15",
    "Sites as much as 1,000 km apart, from the border districts to Somnath and Dwarka",
    "Tracing one vehicle means asking each department separately, by hand",
  ], 0.75, 2.1, 5.5, 4.4, 14);
  card(s, 6.8, 1.6, 6.0, 5.1);
  label(s, "THE LIVE TEST CASE", 7.05, 1.75, 5, 11, C.danger);
  bullets(s, [
    { text: "A registration number is handed over on evaluation day.", bold: true },
    "Identify, trace and present that vehicle's movement across the integrated network",
    "Complete route: timestamped, location-wise, across camera locations and departments",
    "Continuous cross-referencing of live feeds against a watchlist, with automated real-time alerts",
    "A working system. Mock-ups and concept videos are not considered",
  ], 7.05, 2.1, 5.5, 4.4, 14);
}

// ============================================================ 3. MODEL CHOICE
{
  const s = base("Justify the hybrid: Model 1 is mandatory, Model 2 gives analytics without central storage, evidence capture is our addition, Model 3 answers heterogeneity, and Model 4 is ruled out by the bandwidth arithmetic.");
  title(s, "Proposed model: a hybrid, with justification");
  const cols = [
    ["MODEL 1  ·  mandatory", C.accent, ["Camera registry, the control plane", "GIS map, health, gap analysis", "Bulk, manual and API onboarding", "Built and demonstrated"]],
    ["MODEL 2  ·  analytics", C.ok, ["Direct pull, departments untouched", "ANPR metadata, no central video", "Searchable movement records", "Built and demonstrated"]],
    ["EVIDENCE CAPTURE", C.amber, ["Rolling buffer, promote on match only", "60 s clip, SHA-256, audit row", "Validated: 0.54% CPU, flat buffer", "Described in the HLD, next to build"]],
    ["MODEL 3  ·  federation", C.purple, ["Adapter per vendor VMS", "Department-side collector for NAT and SDK-only sites", "Answers heterogeneity, not scale", "Integration path in the HLD"]],
  ];
  cols.forEach(([h, col, items], i) => {
    const x = 0.5 + i * 3.1;
    card(s, x, 1.6, 2.95, 3.9);
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: 1.85, w: 0.35, h: 0.35, fill: { color: col }, line: { color: col, width: 0 } });
    s.addText(h, { x: x + 0.7, y: 1.83, w: 2.2, h: 0.4, fontFace: FONT, fontSize: 12, bold: true, color: C.text, isTextBox: true, margin: 0, valign: "middle" });
    bullets(s, items, x + 0.2, 2.4, 2.6, 3.0, 12);
  });
  card(s, 0.5, 5.75, 12.3, 0.95);
  s.addText([
    { text: "Why not Model 4, fully centralised: ", options: { bold: true, color: C.danger } },
    { text: "80,000 cameras at 3 Mbps is about 240 Gbps sustained into one facility, which is a procurement and physical-plant problem before it is a budget line. Edge analytics cuts what crosses the WAN by roughly 3,750 times, to about 2.1 Mbps of text. [model]", options: { color: C.text } },
  ], { x: 0.75, y: 5.85, w: 11.9, h: 0.75, fontFace: FONT, fontSize: 13, isTextBox: true, margin: 0, valign: "middle" });
}

// ============================================================ 4. WHAT WE BUILT: DASHBOARD
{
  const s = base("This is the Command screen the demo is recorded on. Everything on it is served by the running backend. " + NOTE_CAP);
  title(s, "What we built: the Command view", "One screen: live wall, GIS, live alerts, plate reads, analytics, worker health");
  const h = shot(s, "dashboard.png", 0.5, 1.55, 8.6, "Command view (development capture on a test scenario; live tiles play in the browser)");
  const items = [
    ["Live wall", "Four active-tier tiles, HLS relayed through the backend. Nothing is stored."],
    ["GIS", "30 cameras, coloured by department, health shown by opacity."],
    ["Alerts", "Server-sent events. A watchlist hit lands in about 2 s with its plate crop."],
    ["Plate reads", "Deduplicated sightings, newest first, one click to the route."],
    ["Analytics", "Object counts, intrusion and line-crossing events."],
    ["Workers", "Sustained fps, motion-skip rate, detections per minute per camera."],
  ];
  items.forEach(([h2, t], i) => {
    const y = 1.55 + i * 0.86;
    s.addShape(pres.shapes.OVAL, { x: 9.4, y: y + 0.05, w: 0.32, h: 0.32, fill: { color: C.accent }, line: { color: C.accent, width: 0 } });
    s.addText(String(i + 1), { x: 9.4, y: y + 0.05, w: 0.32, h: 0.32, fontFace: FONT, fontSize: 10, bold: true, color: C.white, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText([{ text: h2 + "  ", options: { bold: true, color: C.text } }, { text: t, options: { color: C.muted } }],
      { x: 9.85, y, w: 3.0, h: 0.8, fontFace: FONT, fontSize: 11, isTextBox: true, margin: 0, valign: "top" });
  });
}

// ============================================================ 5. ARCHITECTURE
{
  const s = base("One pull per camera, three pipelines, the registry underneath. State the governing rule plainly: video is kept only where a logged watchlist match justifies keeping it.");
  title(s, "Architecture: one pull, three pipelines, one registry");
  // registry bar
  card(s, 0.5, 1.5, 12.3, 0.8);
  s.addText([{ text: "MODEL 1 REGISTRY + GIS   ", options: { bold: true, color: C.accent } },
    { text: "the control plane: id, department, location, stream URLs, codec, health, fps tier, ROI, zones. Populated from the catalogue. Nothing downstream hard-codes a camera.", options: { color: C.text } }],
    { x: 0.75, y: 1.55, w: 11.9, h: 0.7, fontFace: FONT, fontSize: 12, isTextBox: true, margin: 0, valign: "middle" });
  // ingest
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 4.9, y: 2.55, w: 3.5, h: 0.6, fill: { color: C.panel2 }, line: { color: C.accent, width: 1 }, rectRadius: 0.1 });
  s.addText("CAMERA GRID  >  ONE pull per camera  >  INGEST WORKER", { x: 4.9, y: 2.55, w: 3.5, h: 0.6, fontFace: FONT, fontSize: 11, bold: true, color: C.text, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  const P = [
    ["PIPELINE 1  ·  LIVE VIEW", C.ok, ["Relay to the control room", "hls.js tiles, backend holds the session", "Persists: NOTHING"], "stores nothing"],
    ["PIPELINE 2  ·  AI ANALYTICS", C.accent, ["Motion gate, detect, track, crop, OCR", "Match against the LOCAL watchlist", "Persists: text rows plus a 2 KB plate crop"], "text and crop only"],
    ["PIPELINE 3  ·  EVIDENCE", C.amber, ["Fixed-size rolling buffer per camera", "Promote 30 s either side, on a watchlist match only", "Persists: clip, SHA-256, audit row"], "on justified cause only"],
  ];
  P.forEach(([h, col, items, foot], i) => {
    const x = 0.5 + i * 4.15;
    s.addShape(pres.shapes.LINE, { x: 6.65, y: 3.15, w: 0, h: 0.35, line: { color: C.border, width: 1 } });
    card(s, x, 3.5, 4.0, 2.55);
    s.addText(h, { x: x + 0.2, y: 3.6, w: 3.6, h: 0.35, fontFace: FONT, fontSize: 12, bold: true, color: col, isTextBox: true, margin: 0 });
    bullets(s, items, x + 0.15, 3.98, 3.7, 1.6, 11);
    s.addText(foot, { x: x + 0.2, y: 5.6, w: 3.6, h: 0.35, fontFace: FONT, fontSize: 11, italic: true, color: C.muted, isTextBox: true, margin: 0 });
  });
  s.addText([{ text: "Governing rule: ", options: { bold: true, color: C.text } },
    { text: "video becomes permanent only where a specific, logged, auditable watchlist match justifies it. This is a civil-liberties position as much as a capacity one, and it maps onto the privacy and auditability bonus criteria.", options: { color: C.muted } }],
    { x: 0.5, y: 6.2, w: 12.3, h: 0.7, fontFace: FONT, fontSize: 12, isTextBox: true, margin: 0 });
}

// ============================================================ 6. MODEL 1: REGISTRY + GIS
{
  const s = base("Every Model 1 deliverable is closed. Disclose that departments and coordinates were assigned: the catalogue carries only id and name. " + NOTE_CAP);
  title(s, "Model 1: registry, GIS and the named deliverables");
  shot(s, "map.png", 0.5, 1.55, 7.6, "GIS view: 30 cameras, coloured by department, with filters and a click-through record (dev capture; basemap tiles load online)");
  card(s, 8.4, 1.55, 4.4, 4.9);
  label(s, "MODEL 1 DELIVERABLES: CLOSED", 8.65, 1.7, 4, 11, C.ok);
  bullets(s, [
    "Working registry portal with a GIS map view",
    "Bulk CSV import with per-row accept and reject, plus manual and API onboarding",
    "Sample onboarded dataset: 30 cameras, 5 departments, 14 live",
    "Registry API documentation: OpenAPI, 26 operations, all described",
    "Gap-analysis report: offline and degraded cameras, plus isolated coverage by nearest-neighbour Haversine",
    "Health monitoring: online, degraded or offline, on a slow cadence",
  ], 8.65, 2.05, 4.0, 3.6, 11.5);
  s.addText("Disclosed: the sandbox catalogue carries only id and name. Departments and coordinates were assigned once in a committed seed file, using real named locations and approximate coordinates, for demonstration.",
    { x: 8.65, y: 5.6, w: 4.0, h: 0.8, fontFace: FONT, fontSize: 10, italic: true, color: C.muted, isTextBox: true, margin: 0 });
}

// ============================================================ 7. FEEDS: REAL FOOTAGE
{
  const s = base("A real frame from the sandbox. Every item on the organisers' pre-submission checklist is implemented and was observed live, including recovery from the CDN's intermittent 403s.");
  title(s, "Consuming the camera grid, as the sandbox actually is");
  shot(s, "feed_cam01.jpg", 0.5, 1.55, 7.2, "cam01 Chimanbhai Bridge, Ahmedabad: a real frame via the session-authenticated HLS path");
  card(s, 8.0, 1.55, 4.8, 5.2);
  label(s, "WHAT WE FOUND, AND HANDLED", 8.25, 1.7, 4.4, 11, C.accent);
  bullets(s, [
    "A session-cookie gate on every path, with non-browser agents rejected. Handled by one shared authenticated session",
    "HLS served as a static 12-hour loop of AES-128 segments, decrypted in-pipeline, with playback position mapped onto one shared timeline for every camera",
    "RTSP over TCP where reachable, HLS fallback recorded per camera in the registry, never UDP",
    "All timing from PTS: 100 frames read with monotonic timestamps, 3 fps sampling verified by PTS span [measured]",
    "Jittered exponential backoff, resync and stream restart on the loop cut, exercised live against real 403s",
    "Consume-only: no publishing, no control API, no footage download",
  ], 8.25, 2.05, 4.4, 4.6, 11);
}

// ============================================================ 8. AI ANALYTICS
{
  const s = base("Real detections on real footage. Licensing is a procurement argument: Apache-2.0 throughout, and deliberately not Ultralytics, which is AGPL.");
  title(s, "Video analytics: ANPR, objects, intrusion, tracking");
  shot(s, "detection.jpg", 0.5, 1.55, 6.4, "Real detections on cam08 Majevadi Gate, Junagadh (YOLOX-S on ONNX Runtime): car, truck, motorcycle, person");
  const steps = [
    ["Motion gate", "MOG2 skips empty frames. Measured skip rate 0 to 83% by camera"],
    ["Detect", "YOLOX or RT-DETR, both Apache-2.0. Never Ultralytics"],
    ["Track", "IoU and centre tracker fed PTS deltas, reset on a scene cut"],
    ["Crop, plate, OCR", "PaddleOCR on the vehicle crop only, with the plate region upscaled"],
    ["Normalise and dedupe", "Indian plate format, 60 s per plate per camera, raw read kept"],
    ["Events", "Object counts, intrusion polygons, directional line crossing"],
  ];
  steps.forEach(([h, t], i) => {
    const y = 1.55 + i * 0.78;
    s.addShape(pres.shapes.OVAL, { x: 7.2, y: y + 0.08, w: 0.34, h: 0.34, fill: { color: C.accent }, line: { color: C.accent, width: 0 } });
    s.addText(String(i + 1), { x: 7.2, y: y + 0.08, w: 0.34, h: 0.34, fontFace: FONT, fontSize: 10, bold: true, color: C.white, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText([{ text: h + "  ", options: { bold: true, color: C.text } }, { text: t, options: { color: C.muted } }],
      { x: 7.7, y, w: 5.1, h: 0.7, fontFace: FONT, fontSize: 11.5, isTextBox: true, margin: 0, valign: "top" });
  });
  card(s, 0.5, 5.6, 6.4, 1.25);
  s.addText([{ text: "Facial recognition: described, not built. ", options: { bold: true, color: C.amber } },
    { text: "Face detection at the edge, then embedding, then matching against an authorised gallery only, with the same edge-cached posture. No general-population face database. Non-match embeddings are not retained. Every match is logged.", options: { color: C.text } }],
    { x: 0.7, y: 5.68, w: 6.0, h: 1.1, fontFace: FONT, fontSize: 10.5, isTextBox: true, margin: 0, valign: "middle" });
  s.addText("Licensing is procurement: Apache-2.0, MIT and BSD throughout. AGPL is hazardous as a linked library and acceptable as a service you run, so Ultralytics YOLO, Elasticsearch and Redis are deliberately avoided.",
    { x: 7.2, y: 6.3, w: 5.6, h: 0.6, fontFace: FONT, fontSize: 10, italic: true, color: C.muted, isTextBox: true, margin: 0 });
}

// ============================================================ 9. WATCHLIST + ALERTS
{
  const s = base("Edge-cached matching is an architectural decision. Central matching at 80,000 cameras is about 1,333 queries per second against VAHAN, which would take down the state's own system of record. " + NOTE_CAP);
  title(s, "Watchlist correlation and real-time alerting");
  shot(s, "alerts.png", 0.5, 1.55, 6.9, "Live alert panel: plate, crop, camera, department, severity, match type, acknowledge (dev capture, test scenario)");
  card(s, 7.7, 1.55, 5.1, 5.2);
  label(s, "METHODOLOGY", 7.95, 1.7, 4.6, 11, C.danger);
  bullets(s, [
    { text: "Matching is local, against a cached watchlist. It is never a per-detection call to VAHAN or eGujCop.", bold: true },
    "Three-step match: exact, then the OCR-ambiguity map (O/0, I/1, S/5, B/8, Z/2, G/6), then Levenshtein 1 or less for reads of 8 characters or more",
    "Partial reads are stored as route candidates and never raise an alert",
    "The sighting is persisted before matching and the alert before broadcast, so a detection never lives only in memory",
    "A five-minute cooldown per plate per camera keeps the feed worth watching",
    "Pushed to the dashboard over Server-Sent Events in about 2 s. The acknowledgement is persisted",
    "Representative watchlist: real observed plates plus invented entries, with provenance recorded",
  ], 7.95, 2.05, 4.7, 4.6, 11);
}

// ============================================================ 10. ROUTE: THE SCORED MOMENT
{
  const s = base("The scored endpoint. Point at departments crossed: a route across Police, GSRTC and Municipal cameras is proof of integration rather than a property of the dataset. " + NOTE_CAP);
  title(s, "Route reconstruction: the scored capability");
  shot(s, "route.png", 0.5, 1.55, 7.8, "Numbered stops in time order, a polyline dashed across coverage gaps, and a timeline with crops (dev capture, test scenario)");
  card(s, 8.6, 1.55, 4.2, 5.2);
  label(s, "GET /api/plates/{plate}/route", 8.85, 1.7, 4, 11, C.accent);
  bullets(s, [
    "Ordered stops: camera, department, coordinates, timestamp, crop, match type",
    "Same-camera dwell collapsed at 2 minutes, so a parked car is one stop",
    "Elapsed time and implied speed between stops as a sanity check: an implausible speed flags the stop as suspect",
    "Fuzzy candidates are surfaced and marked, never silently merged",
    { text: "departments_crossed is the integration proof", bold: true },
    "Coverage gaps are shown rather than hidden, and tie back to the Model 1 gap report",
    "Timestamped detection report as CSV and printable output, the named deliverable",
  ], 8.85, 2.05, 3.8, 4.6, 11);
}

// ============================================================ 11. ZONES + REPORTS
{
  const s = base("Evaluation Area 5 names four analytics. Object and intrusion detection come almost free once the detector is running. " + NOTE_CAP);
  title(s, "Beyond ANPR: intrusion zones, object counts, output reports");
  shot(s, "zones.png", 0.5, 1.55, 6.2, "Zone editor: draw an intrusion polygon or a directional crossing line on a live still, saved as normalised coordinates on the camera");
  shot(s, "reports.png", 6.9, 1.55, 5.9, "Reports: detection report as CSV and printable output, gap analysis, OpenAPI, and per-camera object counts");
  card(s, 0.5, 5.35, 12.3, 1.4);
  bullets(s, [
    "Intrusion: a tracked object's foot point entering a polygon fires once, on entry. Line crossing honours direction, up, down, left or right. High-severity zones broadcast on the alert stream.",
    "Object detection: presence events per camera per class, throttled and aggregated for the dashboard and the report. All coordinates are normalised from 0 to 1, so zones survive a change of resolution.",
  ], 0.75, 5.45, 11.9, 1.25, 11.5);
}

// ============================================================ 12. EDGE VS CENTRALISED
{
  const s = base("This is the number that decides the architecture, and it is also why Model 4 was not chosen. Every figure on this slide is a model from stated assumptions, and is labelled as such.");
  title(s, "Why edge-first: what crosses the WAN at 80,000 cameras", "All figures are [model] from stated assumptions, to be replaced by measurement");
  stat(s, "240 Gbps", "raw video, centralised (1080p at 3 Mbps)", 0.5, 1.9, 4.0, C.danger);
  s.addText(">", { x: 4.5, y: 2.0, w: 1.0, h: 0.9, fontFace: FONT, fontSize: 40, color: C.muted, align: "center", isTextBox: true, margin: 0 });
  stat(s, "2.1 Mbps", "text metadata only, edge-first", 5.5, 1.9, 4.0, C.ok);
  stat(s, "3,750x", "less WAN load", 9.5, 1.9, 3.3, C.accent);
  card(s, 0.5, 3.7, 6.0, 3.0);
  label(s, "GPU FLEET: SIZING FOLLOWS ENGINEERING CHOICES", 0.75, 3.85, 5.5, 10.5, C.accent);
  const rows1 = [["Naive: every frame, full-frame ANPR", "30 / GPU", "2,667 GPUs"], ["5 fps sampling", "50", "1,600"], ["plus motion gating", "100", "800"], ["plus cascade and INT8", "150", "533"], ["plus ROI and tuning", "200", "400"]];
  s.addTable(rows1.map(r => r.map((c, j) => ({ text: c, options: { color: j === 0 ? C.text : C.muted, bold: j === 2, fontSize: 10.5, fontFace: FONT, align: j ? "right" : "left" } }))),
    { x: 0.75, y: 4.2, w: 5.5, colW: [3.3, 1.0, 1.2], rowH: 0.4, border: { type: "solid", color: C.border, pt: 0.5 }, fill: { color: C.panel } });
  card(s, 6.8, 3.7, 6.0, 3.0);
  label(s, "DECODE IS USUALLY THE BINDING CEILING", 7.05, 3.85, 5.5, 10.5, C.danger);
  bullets(s, [
    "Every stream is H.264 or H.265 decoded before any model sees it, and NVDEC caps at roughly 20 to 40 sessions per GPU",
    "At 30 sessions per GPU that is 2,667 GPUs for decode alone, so tuning inference to 200 streams per GPU leaves the tensor cores about 85% idle",
    "Mitigation: decode only the frames you run inference on, prefer H.265, use CPU decode for low-fps tiers, and provision against whichever ceiling binds, measured rather than assumed",
  ], 7.05, 4.2, 5.5, 2.4, 11);
}

// ============================================================ 13. STORAGE
{
  const s = base("The class of data most designs forget, detection snapshots, is 15 times larger than the one they optimise. Store crops, not frames.");
  title(s, "Storage at scale", "Per day, statewide. [model] from one detection per camera per minute; the demo measures the real rate");
  stat(s, "3.46 TB", "detection snapshots as full frames", 0.5, 1.8, 4.0, C.danger);
  stat(s, "0.23 TB", "plate crops of about 2 KB instead, 15 times less", 4.6, 1.8, 4.0, C.ok);
  stat(s, "220 GB", "evidence clips at 10,000 hits per day", 8.7, 1.8, 4.1, C.amber);
  card(s, 0.5, 3.6, 12.3, 3.1);
  bullets(s, [
    { text: "Retention tiers: hot for 7 days, warm for 90, then a cold or frozen archive. Sighting records run to about 115 M per day, 42 billion per year and 21 TB per year indexed, so shard and tier from day one. Retrofitting that after the index is built is a migration with no good window.", },
    "Full frames only for confirmed watchlist hits, where the evidence clip exists anyway. Unmatched sighting crops expire in days rather than years.",
    "Evidence capture: a fixed-size rolling buffer per camera stays flat. Validated at 61 segments in 46 MB, 0.54% of one core and 13.4 s promotion latency [measured, one camera, loopback]. That is roughly 2.2 GB per day per camera-hit budget against about 1,600 GB per day for continuous recording of the same capability.",
    "Each department's own retention policy is honoured, and the platform deliberately keeps metadata for longer than video.",
  ], 0.75, 3.75, 11.9, 2.85, 11.5);
}

// ============================================================ 14. SECURITY, PRIVACY, AUDIT
{
  const s = base("Cybersecurity architecture, Dimension 4, and the privacy posture that separates this from a recording system.");
  title(s, "Cybersecurity, privacy and auditability");
  const items = [
    ["Credentials", "Environment or secret store only. Never hard-coded, logged, persisted or shown unmasked, and no URL carrying a credential is ever written to storage. Vault with per-department rotation in production.", C.accent],
    ["RBAC", "Department-scoped roles, with cross-department access explicit and audited. The demo ships one operator role; production RBAC is designed.", C.purple],
    ["Encryption", "TLS on every hop. Encryption at rest for the evidence store and the databases.", C.ok],
    ["Segmentation", "Edge nodes in department DMZs, central services segmented, least-privilege rules between tiers. Consume-only means no inbound path into a departmental control plane.", C.amber],
    ["Audit", "Every evidence promotion carries an event id, a trigger reason and a SHA-256. Watchlist changes, acknowledgements and cross-department access are all logged. Chain of custody is an output of the system.", C.danger],
    ["Privacy", "Retain nothing by default, promote on justified cause, expire on schedule. Facial recognition only ever against an authorised gallery.", C.text],
  ];
  items.forEach(([h, t, col], i) => {
    const x = 0.5 + (i % 3) * 4.15, y = 1.6 + Math.floor(i / 3) * 2.6;
    card(s, x, y, 4.0, 2.4);
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.22, w: 0.3, h: 0.3, fill: { color: col }, line: { color: col, width: 0 } });
    s.addText(h, { x: x + 0.62, y: y + 0.18, w: 3.2, h: 0.38, fontFace: FONT, fontSize: 13, bold: true, color: C.text, isTextBox: true, margin: 0, valign: "middle" });
    s.addText(t, { x: x + 0.2, y: y + 0.65, w: 3.6, h: 1.65, fontFace: FONT, fontSize: 10.5, color: C.muted, isTextBox: true, margin: 0, valign: "top" });
  });
}

// ============================================================ 15. SCALABILITY, DEPLOYMENT, ROADMAP
{
  const s = base("Edge, regional, central. On day-2 operations: at a 2% failure rate, 1,600 cameras are broken at any moment, so health scoring and a ranked worklist are required rather than optional.");
  title(s, "Deployment, scalability and the phased rollout");
  const tiers = [["EDGE", "district or department", "pull, decode, motion gate, detect, OCR, local watchlist match, ring buffer. Emits text and crops", C.ok],
    ["REGIONAL", "district cluster", "aggregation, regional search index, evidence store, model rollout, camera health scoring", C.accent],
    ["CENTRAL", "SCRB or state data centre", "statewide search, cross-region route correlation, watchlist master, and VAHAN, SARTHI, eGujCop, AFIS and NAFIS enrichment", C.purple]];
  tiers.forEach(([h, sub, t, col], i) => {
    const x = 0.5 + i * 4.15;
    card(s, x, 1.55, 4.0, 2.1);
    s.addText(h, { x: x + 0.2, y: 1.65, w: 3.6, h: 0.35, fontFace: FONT, fontSize: 13, bold: true, color: col, isTextBox: true, margin: 0 });
    s.addText(sub, { x: x + 0.2, y: 1.97, w: 3.6, h: 0.3, fontFace: FONT, fontSize: 10, color: C.muted, isTextBox: true, margin: 0 });
    s.addText(t, { x: x + 0.2, y: 2.3, w: 3.6, h: 1.3, fontFace: FONT, fontSize: 10.5, color: C.text, isTextBox: true, margin: 0 });
  });
  card(s, 0.5, 3.85, 6.5, 2.9);
  label(s, "RESILIENCE AND DAY-2 OPERATIONS", 0.75, 4.0, 6, 10.5, C.danger);
  bullets(s, [
    "Reconnect storms: jittered backoff, admission control, staggered cold start, and a circuit breaker per department",
    "Split-brain ownership: distributed camera leases, so never two pulls and never duplicate alerts",
    "The alert path is the real single point of failure: a durable queue sits before alerting, with synthetic end-to-end tests",
    "A quality score per camera including drift detection, feeding a ranked maintenance worklist. Shadow then canary model rollout. GitOps configuration",
  ], 0.75, 4.32, 6.0, 2.4, 10.5);
  card(s, 7.3, 3.85, 5.5, 2.9);
  label(s, "PHASED STATEWIDE ROLLOUT", 7.55, 4.0, 5, 10.5, C.ok);
  const ph = [["0", "Sandbox, now", "30 to 50 cameras, 5 departments, one node"], ["1", "Pilot district", "one department's real cameras, measured streams per GPU"], ["2", "Multi-district", "3 to 5 departments, federation adapters and collector"], ["3", "Statewide", "towards 80,000 cameras, HA and DR, enrichment integrations"]];
  ph.forEach(([n, h, t], i) => {
    const y = 4.35 + i * 0.58;
    s.addShape(pres.shapes.OVAL, { x: 7.55, y: y + 0.03, w: 0.3, h: 0.3, fill: { color: C.ok }, line: { color: C.ok, width: 0 } });
    s.addText(n, { x: 7.55, y: y + 0.03, w: 0.3, h: 0.3, fontFace: FONT, fontSize: 10, bold: true, color: C.white, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText([{ text: h + "  ", options: { bold: true, color: C.text } }, { text: t, options: { color: C.muted } }], { x: 7.95, y, w: 4.7, h: 0.5, fontFace: FONT, fontSize: 10.5, isTextBox: true, margin: 0 });
  });
}

// ============================================================ 16. WHAT WE DO NOT DO
{
  const s = base("State each of these before the panel has to ask.");
  title(s, "What this system does not do, and why");
  const items = [
    ["No arbitrary rewind, no central recording of all video", "Both the privacy posture and the 240 Gbps arithmetic rule it out. Video is captured on justified cause only."],
    ["No Model 3 federation demonstration", "The sandbox exposes bare stream endpoints, so there are no departmental VMS platforms inside it to federate. Model 3 is documented as the integration path for real departments."],
    ["No live facial recognition", "Described with its privacy controls. Not built, and not claimed."],
    ["Plate recall on these feeds is limited, and stated", "The sandbox cameras are wide traffic-overview PTZ units rather than ANPR lane cameras, so plates sit at 10 to 25 px even on close vehicles. The pipeline upscales the plate region, the demo concentrates on the cameras that read, and the real recall is reported."],
    ["Geography assigned, and disclosed", "The catalogue carries id and name only. Departments and coordinates were assigned once in a committed seed file for demonstration."],
    ["Measured and modelled, labelled", "Every capacity number in the HLD is marked [measured] or [model]. The 30 versus 50 camera discrepancy is recorded rather than resolved silently."],
  ];
  items.forEach(([h, t], i) => {
    const x = 0.5 + (i % 2) * 6.2, y = 1.55 + Math.floor(i / 2) * 1.75;
    card(s, x, y, 6.05, 1.6);
    s.addText(h, { x: x + 0.2, y: y + 0.12, w: 5.7, h: 0.4, fontFace: FONT, fontSize: 12.5, bold: true, color: C.text, isTextBox: true, margin: 0 });
    s.addText(t, { x: x + 0.2, y: y + 0.52, w: 5.7, h: 1.0, fontFace: FONT, fontSize: 10.5, color: C.muted, isTextBox: true, margin: 0 });
  });
}

// ============================================================ 17. OPERATIONAL BENEFITS
{
  const s = base("Close on impact: hours down to seconds, one platform across departments, evidence with a chain of custody, and a cost position the State can own outright.");
  title(s, "Operational benefits and impact on policing");
  const b = [
    ["Hours become seconds", "A registration number returns a timestamped, location-wise route across departments on one screen, instead of a manual request to each of them.", C.accent],
    ["One platform, 26 departments", "Departments keep their systems untouched. The connector ladder and the department-side collector reach vendor-locked and NAT-bound sites.", C.ok],
    ["Alerts operators act on", "Local matching, cooldowns, a plate crop on every alert and an acknowledgement trail. No alert floods and no silent misses.", C.danger],
    ["Evidence that holds up", "Clips promoted on justified cause, each with a SHA-256 and an audit row. Chain of custody comes from how the system is built.", C.amber],
    ["Coverage that stays usable", "Health scoring, drift detection and a ranked maintenance worklist for the 2% of cameras that are always broken.", C.purple],
    ["A cost position the State can own", "Open source under Apache, MIT and BSD, with no per-camera licence, which avoids 4 crore rupees a year at 500 rupees per camera. On-premise deployment avoids recurring cloud egress.", C.text],
  ];
  b.forEach(([h, t, col], i) => {
    const x = 0.5 + (i % 3) * 4.15, y = 1.6 + Math.floor(i / 3) * 2.6;
    card(s, x, y, 4.0, 2.4);
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.22, w: 0.3, h: 0.3, fill: { color: col }, line: { color: col, width: 0 } });
    s.addText(h, { x: x + 0.62, y: y + 0.18, w: 3.25, h: 0.4, fontFace: FONT, fontSize: 12.5, bold: true, color: C.text, isTextBox: true, margin: 0, valign: "middle" });
    s.addText(t, { x: x + 0.2, y: y + 0.65, w: 3.6, h: 1.65, fontFace: FONT, fontSize: 10.5, color: C.muted, isTextBox: true, margin: 0 });
  });
}

// ============================================================ 18. DELIVERABLES + LINKS
{
  const s = base("Final slide: the submission package. Fill in the links before export and open every one from a private window.");
  title(s, "Submission package");
  card(s, 0.5, 1.55, 6.0, 5.2);
  label(s, "DELIVERED", 0.75, 1.7, 5, 11, C.ok);
  bullets(s, [
    "Solution presentation: this deck, as PDF",
    "Technical proposal and HLD: all eight required elements and the ten dimensions, with measured and modelled figures labelled, as PDF",
    "Demo video 1, own feed: onboarding, detection, watchlist correlation, automatic alert",
    "Demo video 2, government-provided feed: onboarding, viewing, analytics output and timestamped detection report",
    "Registry API documentation (OpenAPI), sample onboarded dataset, gap-analysis report, detection report as CSV and PDF",
    "Source repository: Python 3.11 with FastAPI and SQLite for the demo, React with Leaflet and hls.js, YOLOX and PaddleOCR under Apache-2.0",
  ], 0.75, 2.05, 5.5, 4.6, 11.5);
  card(s, 6.8, 1.55, 6.0, 5.2);
  label(s, "LINKS", 7.05, 1.7, 5, 11, C.accent);
  bullets(s, [
    "Demo video 1 (unlisted): [link]",
    "Demo video 2 (unlisted): [link]",
    "Source repository: [link]",
    "Hosted platform and test credentials (optional): [link]",
    "HLD (PDF): [link]",
  ], 7.05, 2.05, 5.5, 2.6, 12);
  s.addText("Every link verified from a private window. No credential appears in the repository, its history, any video frame or any screenshot.",
    { x: 7.05, y: 4.9, w: 5.5, h: 0.8, fontFace: FONT, fontSize: 10.5, italic: true, color: C.muted, isTextBox: true, margin: 0 });
  s.addText("Sentinel: one platform, five departments, watching is not storing.", { x: 7.05, y: 5.9, w: 5.5, h: 0.6, fontFace: FONT, fontSize: 13, bold: true, color: C.text, isTextBox: true, margin: 0 });
}

pres.writeFile({ fileName: path.join(__dirname, "..", "Sentinel-Solution-Presentation.pptx") })
  .then((f) => console.log("wrote", f));
