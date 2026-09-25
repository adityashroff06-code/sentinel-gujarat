// Sentinel: Solution Presentation. Build: npm install && node build_deck.js
// Output: ../Sentinel-Solution-Presentation.pptx
// S5.2 rebuild (25 Sep 2026): every UI image is a capture of the running
// platform at 1920x1080 (data/screens/deck-*.png, copied into img/), and
// every claim follows the corrected HLD (deliverables/HLD.md is the source
// of truth). [measured] is used only for the six figures of the S4.1 run.
const pptxgen = require("pptxgenjs");
const path = require("path");

const IMG = (f) => path.join(__dirname, "img", f);
const C = {
  bg: "0A0E14", panel: "111823", panel2: "16202E", border: "1E2A3A",
  text: "E6EDF5", muted: "8A97A6", accent: "3D7FD6", danger: "D64F6A",
  ok: "39A56A", amber: "E0912F", purple: "B45FD1", white: "FFFFFF",
};
const FONT = "Calibri";
const REPO_URL = "https://github.com/adityashroff06-code/sentinel-gujarat";

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
// every screenshot is a 1920x1080 capture, so 16:9 holds
function shot(s, file, x, y, w, caption) {
  const h = w * 9 / 16;
  s.addImage({ path: IMG(file), x, y, w, h, rounding: false });
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.bg, transparency: 100 },
    line: { color: C.border, width: 0.75 } });
  if (caption) s.addText(caption, { x, y: y + h + 0.06, w, h: 0.4, fontFace: FONT,
    fontSize: 9, color: C.muted, isTextBox: true, margin: 0, valign: "top" });
  return h;
}
function pill(s, t, x, y, color) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.15, h: 0.3, fill: { color },
    line: { color, width: 0 }, rectRadius: 0.15 });
  s.addText(t, { x, y, w: 1.15, h: 0.3, fontFace: FONT, fontSize: 10, bold: true,
    color: C.white, align: "center", valign: "middle", isTextBox: true, margin: 0 });
}
const LIVE = "Captured from the running platform on 25 September 2026 (1920x1080, signed in through the script key path; no credential is on screen).";

// ============================================================ 1. TITLE
{
  const s = base("Open with the sentence that is graded: a registration number handed over live returns that vehicle's complete timestamped route across the network.");
  s.addText("SENTINEL", { x: 0.7, y: 1.6, w: 12, h: 1.1, fontFace: FONT, fontSize: 60,
    bold: true, color: C.text, isTextBox: true, margin: 0, charSpacing: 6 });
  s.addText("Integrated Video Management and Analytics Platform", { x: 0.7, y: 2.7, w: 12,
    h: 0.6, fontFace: FONT, fontSize: 24, color: C.text, isTextBox: true, margin: 0 });
  s.addText("A hybrid of Model 1 (Centralised CCTV Registry and GIS Mapping) and Model 2 (Unified Viewing and Metadata Analytics), with event-triggered evidence capture (Pipeline 3) designed and validated separately. Model 3 federation is the documented integration path.",
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
  const s = base("Justify the hybrid: Model 1 is mandatory, Model 2 gives unified viewing and analytics without central storage, Pipeline 3 evidence capture is designed and validated separately and is not built in the demo, Model 3 answers heterogeneity, and Model 4 is ruled out by the bandwidth arithmetic.");
  title(s, "Proposed model: a hybrid, with justification");
  const cols = [
    ["MODEL 1  ·  mandatory", C.accent, ["Camera registry, the control plane", "GIS console: department layers, coverage sectors, activity, gaps", "Onboarding by form, CSV and API", "Built and demonstrated"]],
    ["MODEL 2  ·  viewing + analytics", C.ok, ["Direct pull, departments untouched", "Two different systems in one viewer", "ANPR metadata, no central video", "Built and demonstrated"]],
    ["PIPELINE 3  ·  evidence", C.amber, ["Rolling buffer, promote on a match only", "60 s clip, SHA-256, audit row", "Designed and validated separately", "Not built in the demo"]],
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
    { text: "Why not Model 4, Central VMS and AI Platform: ", options: { bold: true, color: C.danger } },
    { text: "80,000 cameras at 3 Mbps is about 240 Gbps sustained into one facility, a procurement and physical-plant problem before it is a budget line. Analysing at the edge sends only text rows and plate crops, about 23 Mbps, roughly 10,000 times less. [model]", options: { color: C.text } },
  ], { x: 0.75, y: 5.85, w: 11.9, h: 0.75, fontFace: FONT, fontSize: 13, isTextBox: true, margin: 0, valign: "middle" });
}

// ============================================================ 4. WHAT WE BUILT: COMMAND
{
  const s = base("This is the Command screen the demo opens on, captured from the running platform. Three sandbox cameras are pulled live over RTSP and one tile is a local sample feed; all four play through the relay. The Start-here panel tells the evaluator which data is demonstration data. " + LIVE);
  title(s, "What we built: the Command view", "One screen: live tiles, GIS, alerts, plate reads, analytics and feed health, all served by the operational backend");
  shot(s, "dashboard.png", 0.5, 1.55, 8.6, "Command view, live: sandbox cameras cam09, cam27 and cam28 over RTSP and sample feed local01, all through the relay (captured 25 Sep 2026)");
  const items = [
    ["Live tiles", "Analysed feeds relayed, not recorded: a self-overwriting 20 s window is the only video on disk."],
    ["GIS", "58 cameras: the organisers' 30 and 28 local sample feeds, clustered by city."],
    ["Alerts", "Alert rows tailed from the database and pushed over Server-Sent Events in about 2 s [estimate]."],
    ["Feed status", "Reading, no traffic or feed down, judged by each pull's own freshness."],
    ["Start here", "The first screen says which data is demonstration data. Demo rows carry a DEMO badge."],
    ["Reads and analytics", "Latest plate reads, object, person and zone-event counts from the live detector."],
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
  const s = base("One pull per camera, three pipelines, the registry underneath. Pipelines 1 and 2 are built; Pipeline 3 is designed and validated separately and is not built in the demo. State the governing rule plainly: video is kept only where a logged watchlist match justifies keeping it, and in the demo no video is kept beyond the 20-second relay window.");
  title(s, "Architecture: one pull, three pipelines, one registry");
  card(s, 0.5, 1.5, 12.3, 0.8);
  s.addText([{ text: "MODEL 1 REGISTRY + GIS   ", options: { bold: true, color: C.accent } },
    { text: "the control plane: id, department, location, bearing, field of view, stream URLs (never credentials), codec, health, tier, zones. Nothing downstream hard-codes a camera.", options: { color: C.text } }],
    { x: 0.75, y: 1.55, w: 11.9, h: 0.7, fontFace: FONT, fontSize: 12, isTextBox: true, margin: 0, valign: "middle" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 4.6, y: 2.55, w: 4.1, h: 0.6, fill: { color: C.panel2 }, line: { color: C.accent, width: 1 }, rectRadius: 0.1 });
  s.addText("CAMERA GRID  >  ONE pull per camera (RTSP over TCP)  >  NODE", { x: 4.6, y: 2.55, w: 4.1, h: 0.6, fontFace: FONT, fontSize: 11, bold: true, color: C.text, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  const P = [
    ["PIPELINE 1  ·  LIVE VIEW", C.ok, ["Relay to the control room: Command and the Live Wall", "hls.js tiles; the API holds the upstream session", "Persists: a self-overwriting 20 s relay window only"], "relayed, not recorded  ·  built"],
    ["PIPELINE 2  ·  AI ANALYTICS", C.accent, ["Motion gate, detect, track, crop, OCR", "Match against the LOCAL cached watchlist", "Persists: text rows plus a plate crop of about 2 KB"], "text and crop only  ·  built"],
    ["PIPELINE 3  ·  EVIDENCE", C.amber, ["Fixed-size rolling buffer per camera", "Promote 30 s either side, on a watchlist match only", "Persists: clip, SHA-256, audit row"], "designed and validated separately; not built in the demo"],
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
    { text: "video becomes permanent only where a specific, logged, auditable watchlist match justifies it. In the demonstrated system, where Pipeline 3 is not built, no video is kept beyond the 20-second relay window.", options: { color: C.muted } }],
    { x: 0.5, y: 6.2, w: 12.3, h: 0.7, fontFace: FONT, fontSize: 12, isTextBox: true, margin: 0 });
}

// ============================================================ 6. MODEL 1: REGISTRY + GIS
{
  const s = base("Every Model 1 deliverable is built. The left capture is the whole registry on the GIS console; the right is zoomed to Gandhinagar with a camera's record open, showing field-of-view sectors and 24-hour read activity. Disclose that departments and coordinates were assigned: the catalogue carries only id and name, and the 28 sample feeds are stock footage at seeded coordinates. " + LIVE);
  title(s, "Model 1: registry, GIS console and the named deliverables");
  shot(s, "map.png", 0.5, 1.5, 6.05, "GIS console, live: all 58 cameras clustered by city, department layers, basemap choice and legend");
  shot(s, "gis.png", 6.75, 1.5, 6.05, "Zoomed to Gandhinagar: pins by department, field-of-view sectors, 24 h read activity and the camera's registry record");
  card(s, 0.5, 5.35, 12.3, 1.55);
  label(s, "MODEL 1 DELIVERABLES: BUILT", 0.75, 5.43, 5, 10.5, C.ok);
  bullets(s, [
    "Registry portal with a GIS console: street, light and satellite basemaps; department layers, coverage sectors, activity, cluster hulls, coverage gaps",
    "Onboarding by form, bulk CSV (each row accepted or rejected with a reason) and POST /api/cameras, every action audited",
  ], 0.75, 5.72, 5.9, 1.15, 10.5);
  bullets(s, [
    "58 cameras registered: the organisers' 30 across 5 departments and 28 local sample feeds; registry API documented as OpenAPI; gap-analysis report; health monitoring",
    { text: "Disclosed: the catalogue carries only id and name. Departments and coordinates of the sandbox cameras and of the sample feeds are seeded in committed files.", color: C.muted },
  ], 6.8, 5.72, 5.85, 1.15, 10.5);
}

// ============================================================ 7. MODEL 2: TWO SYSTEMS, ONE VIEWER
{
  const s = base("The Model 2 deliverable: two different systems in one viewer. System A is the organisers' sandbox gateway, pulled live over RTSP, one pull per camera; system B is a local mediamtx server publishing 28 stock-footage feeds. Every item on the organisers' pre-submission checklist is implemented. The H.265 sandbox tiles need a browser that decodes HEVC; the capture on the left was taken in Chrome. " + LIVE);
  title(s, "Model 2: two different systems in one viewer");
  shot(s, "wall.png", 0.5, 1.5, 6.05, "System A, the organisers' sandbox: four analysed cameras pulled live over RTSP and played through the relay");
  shot(s, "wall-local.png", 6.75, 1.5, 6.05, "System B, a local camera server: 28 stock-footage feeds (sample clips at seeded coordinates, labelled on every tile)");
  card(s, 0.5, 5.35, 12.3, 1.55);
  bullets(s, [
    "One pull per camera, RTSP over TCP and never UDP; decoder warnings on join are logged, never fatal",
    "All timing from PTS; jittered exponential backoff (2 s base, 30 s cap) and a stall watchdog on every pull",
    "Consume-only: no publishing, no control-API calls, no footage download",
  ], 0.75, 5.47, 5.9, 1.4, 10.5);
  bullets(s, [
    "Every registered camera opens on the Live Wall through the relay: the node's own pull, the organisers' CDN recording, or the local server's HLS",
    "Only the tiles on screen hold a stream; the relay sits behind the login and is rate-limited",
    "The sample feeds are stock footage, not sandbox footage and not filmed by the team",
  ], 6.8, 5.47, 5.85, 1.4, 10.5);
}

// ============================================================ 8. AI ANALYTICS
{
  const s = base("Real plate reads on a government feed: cam06 on the live sandbox, with the OCR text kept beside the coerced plate. The measured figures are the only [measured] numbers in the submission, from the formal 10-minute run on 25 September. " + LIVE);
  title(s, "Video analytics: ANPR, objects, intrusion, tracking");
  shot(s, "search.png", 0.5, 1.55, 6.4, "ANPR on the live sandbox: every read of GJ11S7924 on cam06, the OCR text kept beside the coerced plate, with crop, confidence, class and provenance");
  const steps = [
    ["Motion gate", "MOG2 skips static frames; measured skip rate 0 to 54% by camera [measured]"],
    ["Detect", "YOLOX-S (Apache-2.0) on ONNX Runtime, on the GPU through DirectML. Never Ultralytics (AGPL)"],
    ["Track", "A greedy IoU and centre-distance tracker on PTS deltas: an IoU tracker, not ByteTrack"],
    ["Crop and OCR", "The vehicle crop, never the frame, upscaled and read by PaddleOCR PP-OCRv5 mobile"],
    ["Plate grammar", "Indian format with position-aware coercion (GJ1157924 stored as GJ11S7924); a track's reads are voted; raw OCR kept"],
    ["Events", "Object and person counts, intrusion polygons, directional line crossing"],
  ];
  steps.forEach(([h, t], i) => {
    const y = 1.55 + i * 0.68;
    s.addShape(pres.shapes.OVAL, { x: 7.2, y: y + 0.06, w: 0.32, h: 0.32, fill: { color: C.accent }, line: { color: C.accent, width: 0 } });
    s.addText(String(i + 1), { x: 7.2, y: y + 0.06, w: 0.32, h: 0.32, fontFace: FONT, fontSize: 10, bold: true, color: C.white, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText([{ text: h + "  ", options: { bold: true, color: C.text } }, { text: t, options: { color: C.muted } }],
      { x: 7.7, y, w: 5.1, h: 0.64, fontFace: FONT, fontSize: 11, isTextBox: true, margin: 0, valign: "top" });
  });
  card(s, 7.2, 5.72, 5.6, 1.18);
  s.addText([{ text: "MEASURED ON THE LIVE SANDBOX, 25 SEP  ", options: { bold: true, color: C.ok } },
    { text: "(10-minute run, five cameras over RTSP, laptop GTX 1650): inference 0.6 to 1.5 fps per camera; peak GPU memory 119 MiB; peak RAM 1,749 MB; plate-read rate 0.062 [measured]. The ANPR viability gate passed; the binding stage was CPU OCR, not the GPU.", options: { color: C.text } }],
    { x: 7.35, y: 5.78, w: 5.3, h: 1.08, fontFace: FONT, fontSize: 10, isTextBox: true, margin: 0, valign: "middle" });
  card(s, 0.5, 5.72, 6.4, 1.18);
  s.addText([{ text: "Facial recognition: described, not built. ", options: { bold: true, color: C.amber } },
    { text: "Face detection at the edge, then embedding, then matching against an authorised gallery only, with the same edge-cached posture. No general-population face database. Non-match embeddings are not retained. Every match is logged.", options: { color: C.text } }],
    { x: 0.7, y: 5.78, w: 6.0, h: 1.08, fontFace: FONT, fontSize: 10.5, isTextBox: true, margin: 0, valign: "middle" });
}

// ============================================================ 9. WATCHLIST + ALERTS
{
  const s = base("Edge-cached matching is an architectural decision. Central matching at 80,000 cameras is about 1,333 queries per second against VAHAN [model], which would take down the state's own system of record. The alerts shown are for the labelled demonstration vehicle, injected through the real write path. " + LIVE);
  title(s, "Watchlist correlation and real-time alerting");
  shot(s, "alerts.png", 0.5, 1.5, 6.05, "Alert stream: plate crop, severity, category, match type and a DEMO badge on every demonstration row");
  shot(s, "search-ambiguity.png", 6.75, 1.5, 6.05, "A mistyped query (GJ01A81234) still finds the watchlisted vehicle: the 8/B look-alike is corrected by position");
  card(s, 0.5, 5.35, 12.3, 1.55);
  bullets(s, [
    { text: "Matching is local, against a cached watchlist: never a per-detection call to VAHAN or eGujCop", bold: true },
    "Three match types in order: exact, OCR-ambiguity (O/0, I/1, S/5, B/8, Z/2, G/6, Q/0), then confusion-weighted fuzzy",
    "Alerts fire on exact and ambiguity; fuzzy is shown and flagged, not alerted by default; partial reads never alert",
  ], 0.75, 5.45, 5.9, 1.42, 10.5);
  bullets(s, [
    "Sighting written before matching; alert row written before broadcast; the API tails the alerts table and pushes Server-Sent Events",
    "Five-minute cooldown per plate per camera, derived from the database rather than process memory",
    "Acknowledgements persisted and audited under the operator's name; every plate lookup is audited too",
  ], 6.8, 5.45, 5.85, 1.42, 10.5);
}

// ============================================================ 10. ROUTE: THE SCORED MOMENT
{
  const s = base("The scored endpoint. The route shown is the labelled demonstration vehicle, injected through the real write path at three sandbox cameras in three departments; no real vehicle has yet been read on two sandbox cameras, and the slide says so. Point at departments crossed: a route across Police, GSRTC and Municipal cameras is proof of integration. " + LIVE);
  title(s, "Route reconstruction: the scored capability");
  shot(s, "route.png", 0.5, 1.55, 7.8, "GJ01AB1234, the labelled demonstration vehicle: 4 stops, 3 cameras, 3 departments, numbered in time order with crops and implied speeds");
  card(s, 8.6, 1.55, 4.2, 5.35);
  label(s, "GET /api/plates/{plate}/route", 8.85, 1.7, 4, 11, C.accent);
  bullets(s, [
    "Ordered stops: camera, department, coordinates, timestamp, crop, match type and provenance",
    "Elapsed time and implied speed only within one clock; an implausible speed flags the stop as suspect",
    "Fuzzy candidates are surfaced and marked, never silently merged",
    { text: "departments_crossed is the integration proof", bold: true },
    "Coverage gaps are shown rather than hidden",
    "Route export and detection report as CSV and printable HTML, each with a provenance column",
    { text: "Disclosed: no real vehicle has been read on two sandbox cameras. The route shown is demonstration data, labelled DEMO on every screen and export.", color: C.amber },
  ], 8.85, 2.05, 3.8, 4.8, 10.5);
}

// ============================================================ 11. ZONES + REPORTS
{
  const s = base("Evaluation Area 5 names four analytics. Object and person detection come with the detector; intrusion and line crossing come from zones drawn on the live picture. The crossing line on cam06 is the one that produced the first zone events on a real feed. " + LIVE);
  title(s, "Beyond ANPR: intrusion zones, object counts, output reports");
  shot(s, "zones.png", 0.5, 1.5, 6.05, "Zone editor on the live cam06 picture: the crossing line that fired 53 line-crossing events on the live sandbox during the measured afternoon run");
  shot(s, "reports.png", 6.75, 1.5, 6.05, "Reports: detection report as CSV and printable HTML, gap analysis, OpenAPI; object counts per camera; every row labelled live or demo");
  card(s, 0.5, 5.35, 12.3, 1.55);
  bullets(s, [
    "Intrusion: a tracked object's foot point must be inside a zone for two consecutive sampled frames before it fires; a line crossing is measured against the last confirmed side, with direction. High-severity zones raise alerts on the same stream.",
    "Object and person detection: per-class events, throttled to one per class per camera every 5 s of stream time, counted on Command and in Reports. Zones are stored in normalised 0 to 1 coordinates, so they survive a change of resolution.",
  ], 0.75, 5.45, 11.9, 1.42, 11);
}

// ============================================================ 12. EDGE VS CENTRALISED
{
  const s = base("This is the number that decides the architecture, and it is also why Model 4 was not chosen. Every figure on this slide is a model from stated assumptions, and is labelled as such.");
  title(s, "Why edge-first: what crosses the WAN at 80,000 cameras", "All figures are [model], from one plate read per camera per minute, to be replaced by measurement in the pilot");
  stat(s, "240 Gbps", "raw video, centralised (1080p at 3 Mbps)", 0.5, 1.9, 4.0, C.danger);
  s.addText(">", { x: 4.5, y: 2.0, w: 1.0, h: 0.9, fontFace: FONT, fontSize: 40, color: C.muted, align: "center", isTextBox: true, margin: 0 });
  stat(s, "23 Mbps", "text rows and plate crops, edge-first", 5.5, 1.9, 4.0, C.ok);
  stat(s, "10,000x", "less WAN load", 9.5, 1.9, 3.3, C.accent);
  card(s, 0.5, 3.7, 6.0, 3.0);
  label(s, "GPU FLEET: SIZING FOLLOWS ENGINEERING CHOICES [model]", 0.75, 3.85, 5.5, 10.5, C.accent);
  const rows1 = [["Naive: every frame, full-frame ANPR", "30 / GPU", "2,667 GPUs"], ["5 fps sampling", "50", "1,600"], ["plus motion gating", "100", "800"], ["plus cascade and INT8", "150", "533"], ["plus ROI and tuning", "200", "400"]];
  s.addTable(rows1.map(r => r.map((c, j) => ({ text: c, options: { color: j === 0 ? C.text : C.muted, bold: j === 2, fontSize: 10.5, fontFace: FONT, align: j ? "right" : "left" } }))),
    { x: 0.75, y: 4.2, w: 5.5, colW: [3.3, 1.0, 1.2], rowH: 0.4, border: { type: "solid", color: C.border, pt: 0.5 }, fill: { color: C.panel } });
  card(s, 6.8, 3.7, 6.0, 3.0);
  label(s, "DECODE IS USUALLY THE BINDING CEILING", 7.05, 3.85, 5.5, 10.5, C.danger);
  bullets(s, [
    "Every stream is H.264 or H.265 decoded before any model sees it, and decode engines cap at roughly 20 to 40 sessions per GPU [estimate]",
    "At 30 per GPU, decode alone needs 2,667 GPUs, so tuning inference to 200 streams per GPU leaves the tensor cores about 85% idle [model]",
    "Mitigation: decode only the frames that are inferred, prefer H.265, CPU-decode low-fps tiers, provision against the ceiling that binds",
    "The laptop run adds a lesson: its binding stage was OCR on the CPU, so a node budgets OCR on the accelerator too",
  ], 7.05, 4.2, 5.5, 2.45, 10.5);
}

// ============================================================ 13. STORAGE
{
  const s = base("The class of data most designs forget, detection snapshots, is 15 times larger than the one they optimise. Store crops, not frames. Every figure here is a model.");
  title(s, "Storage at scale", "Per day, statewide. [model] from one plate read per camera per minute");
  stat(s, "3.46 TB", "detection snapshots as full frames", 0.5, 1.8, 4.0, C.danger);
  stat(s, "0.23 TB", "plate crops of about 2 KB instead, 15 times less", 4.6, 1.8, 4.0, C.ok);
  stat(s, "220 GB", "evidence clips at 10,000 hits per day", 8.7, 1.8, 4.1, C.amber);
  card(s, 0.5, 3.6, 12.3, 3.1);
  bullets(s, [
    "Retention tiers: hot for 7 days, warm for 90, then a cold or frozen archive. Sighting records run to about 115 million a day, 42 billion a year and 21 TB a year indexed [model], so shard and tier from day one. Retrofitting that after the index is built is a migration with no good window.",
    "Full frames only for confirmed watchlist hits, where the evidence clip exists anyway. Unmatched sighting crops expire in days rather than years.",
    "Evidence capture (Pipeline 3) is designed and validated separately and is not built in the demo: a fixed-size rolling buffer per camera stays flat and promotes a hashed clip only on a match. In the demo, the only video on disk is the self-overwriting 20-second relay window per analysed camera.",
    "Retention by data class, purged on a schedule: proposed non-hit crops 30 days, sighting rows 180 days, hit evidence for the life of the case [estimate]. Each department's own 7 to 15-day video retention is untouched. The purge is part of the pilot build.",
  ], 0.75, 3.75, 11.9, 2.85, 11.5);
}

// ============================================================ 14. SECURITY, PRIVACY, AUDIT
{
  const s = base("Cybersecurity architecture, Dimension 4. Login, roles, sessions and the audit trail are built and running on the demonstrated platform; department scoping and the vault are the production additions.");
  title(s, "Cybersecurity, privacy and auditability");
  const items = [
    ["Credentials", "Environment or secret store only. Never hard-coded, logged, persisted or shown unmasked; the registry holds URL templates with placeholders filled in memory. A vault with per-department rotation in production.", C.accent],
    ["Login and roles (built)", "People sign in as viewer, evaluator or admin. Passwords only as scrypt hashes; server-side sessions in HttpOnly, SameSite=Strict cookies expiring after 8 h; lockout after five failures. Department scoping is added in production.", C.purple],
    ["Encryption", "TLS on every hop the platform controls. When the demo is published, it goes out over an outbound-only tunnel with TLS terminated on the laptop. Encryption at rest for the evidence store and the databases in production.", C.ok],
    ["Hardening (built)", "Nothing is reachable without signing in except the login page, /api/health and static assets. Content-Security-Policy, nosniff, frame denial, rate limits on expensive reads. Only the API port is published.", C.amber],
    ["Audit (built)", "An append-only audit table names the user for every onboarding, watchlist change, acknowledgement, zone edit and login, and for every plate lookup, search and route export. Pipeline 3 adds hashed evidence rows.", C.danger],
    ["Privacy", "Relayed, not recorded: text and a 2 KB crop per read. Retention by data class, designed to the DPDP Act, 2023 duties. Facial recognition only ever against an authorised gallery.", C.text],
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
  const s = base("Edge, regional, central. On day-2 operations: at a 2% failure rate, about 1,600 cameras are broken at any moment [model], so health scoring and a ranked worklist are required rather than optional.");
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
    "The alert path is the real single point of failure: detections are persisted before alerting, with synthetic end-to-end tests",
    "A quality score per camera including drift detection, feeding a ranked maintenance worklist. Shadow then canary model rollout. GitOps configuration",
  ], 0.75, 4.32, 6.0, 2.4, 10.5);
  card(s, 7.3, 3.85, 5.5, 2.9);
  label(s, "PHASED STATEWIDE ROLLOUT", 7.55, 4.0, 5, 10.5, C.ok);
  const ph = [["0", "Sandbox, now", "30 sandbox cameras and 28 sample feeds, one node"], ["1", "Pilot district", "one department's real cameras, measured streams per accelerator, Pipeline 3 built"], ["2", "Multi-district", "3 to 5 departments, federation adapters and collector"], ["3", "Statewide", "towards 80,000 cameras, HA and DR, enrichment integrations"]];
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
    ["No evidence clips in the demonstrated system", "Pipeline 3 is designed and validated separately and is not built. No alert links a clip, and no video is kept beyond the 20-second relay window."],
    ["No arbitrary rewind, no central recording of all video", "Both the privacy posture and the 240 Gbps arithmetic rule it out. Video is captured on justified cause only."],
    ["No real cross-camera route on the sandbox feeds", "No real vehicle has been read on two sandbox cameras. The route shown is a demonstration vehicle labelled DEMO everywhere; the scored test uses the organisers' own vehicle."],
    ["No Model 3 federation, no live facial recognition", "The sandbox holds no departmental VMS to federate, so Model 3 is the documented integration path. Facial recognition is described with its privacy controls, not built and not claimed."],
    ["Plate recall on these feeds is low, and stated", "Wide overview cameras put plates at 10 to 25 px [estimate]. Plate-read rate 0.062, 12 reads in 195 vehicle tracks [measured]; cam06 gave 55 real reads over the afternoon, and the ANPR viability gate passed on that evidence."],
    ["Demonstration data, disclosed", "Sandbox geography is seeded (the catalogue has id and name only); the 28 sample feeds are stock footage at seeded coordinates; the demo vehicle is labelled. Figures are marked [measured], [model] or [estimate]; the 30 versus 50 camera gap is recorded."],
  ];
  items.forEach(([h, t], i) => {
    const x = 0.5 + (i % 2) * 6.2, y = 1.55 + Math.floor(i / 2) * 1.75;
    card(s, x, y, 6.05, 1.6);
    s.addText(h, { x: x + 0.2, y: y + 0.12, w: 5.7, h: 0.4, fontFace: FONT, fontSize: 12.5, bold: true, color: C.text, isTextBox: true, margin: 0 });
    s.addText(t, { x: x + 0.2, y: y + 0.52, w: 5.7, h: 1.0, fontFace: FONT, fontSize: 10.5, color: C.muted, isTextBox: true, margin: 0, valign: "top" });
  });
}

// ============================================================ 17. OPERATIONAL BENEFITS
{
  const s = base("Close on impact: hours down to seconds, one platform across departments, an audit trail on every lookup, and a cost position the State can own outright.");
  title(s, "Operational benefits and impact on policing");
  const b = [
    ["Hours become seconds", "A registration number returns a timestamped, location-wise route across departments on one screen, instead of a manual request to each of them.", C.accent],
    ["One platform, 26 departments", "Departments keep their systems untouched. The connector ladder and the department-side collector reach vendor-locked and NAT-bound sites.", C.ok],
    ["Alerts operators act on", "Local matching, cooldowns, a plate crop on every alert and an acknowledgement trail. No alert floods, and no neighbour's car alerted on a fuzzy read.", C.danger],
    ["Evidence that holds up", "Built: every lookup, change and acknowledgement is audited under a named user. Designed for the pilot: clips promoted on justified cause, each with a SHA-256 and an audit row.", C.amber],
    ["Coverage that stays usable", "Health scoring, drift detection and a ranked maintenance worklist for the roughly 2% of cameras that are always broken [model].", C.purple],
    ["A cost position the State can own", "Linked components are Apache, MIT and BSD; ffmpeg runs as a separate GPL process. No per-camera licence avoids about 4 crore rupees a year at 500 rupees per camera [model]. On-premise avoids cloud egress.", C.text],
  ];
  b.forEach(([h, t, col], i) => {
    const x = 0.5 + (i % 3) * 4.15, y = 1.6 + Math.floor(i / 3) * 2.6;
    card(s, x, y, 4.0, 2.4);
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.22, w: 0.3, h: 0.3, fill: { color: col }, line: { color: col, width: 0 } });
    s.addText(h, { x: x + 0.62, y: y + 0.18, w: 3.25, h: 0.4, fontFace: FONT, fontSize: 12.5, bold: true, color: C.text, isTextBox: true, margin: 0, valign: "middle" });
    s.addText(t, { x: x + 0.2, y: y + 0.65, w: 3.6, h: 1.65, fontFace: FONT, fontSize: 10.5, color: C.muted, isTextBox: true, margin: 0, valign: "top" });
  });
}

// ============================================================ 18. DELIVERABLES + LINKS
{
  const s = base("Final slide: the submission package. The video links and the hosted URL are added at submission, after each is opened from a private window; evaluator credentials go on the submission form only, never in the deck or the repository.");
  title(s, "Submission package");
  card(s, 0.5, 1.55, 6.0, 5.2);
  label(s, "DELIVERED", 0.75, 1.7, 5, 11, C.ok);
  bullets(s, [
    "Solution presentation: this deck, as PPTX and PDF",
    "Technical proposal and HLD: the eight required elements and the ten dimensions, with measured, modelled and estimated figures labelled, as PDF",
    "Workflow and integration diagram (SVG, PNG and PDF)",
    "Demo video 1, own feed: onboarding, detection, watchlist correlation, automatic alert",
    "Demo video 2, government-provided feed: viewing, ANPR with crops, vehicle and person detection, line crossing, detection report",
    "Registry API documentation (OpenAPI), sample onboarded dataset, gap-analysis report, detection report as CSV and HTML",
    "Source repository: Python 3.13 with FastAPI and SQLite for the demo, React with Leaflet and hls.js, YOLOX-S and PaddleOCR under Apache-2.0",
  ], 0.75, 2.05, 5.5, 4.6, 11);
  card(s, 6.8, 1.55, 6.0, 5.2);
  label(s, "LINKS", 7.05, 1.7, 5, 11, C.accent);
  const link = (lbl, url, shown) => [
    { text: lbl, options: { bullet: true, color: C.text } },
    { text: shown, options: { color: C.accent, hyperlink: { url }, breakLine: true } },
  ];
  const plain = (lbl, t, last) => [
    { text: lbl, options: { bullet: true, color: C.text } },
    { text: t, options: { color: C.muted, breakLine: !last } },
  ];
  s.addText([
    ...link("Source repository: ", REPO_URL, "github.com/adityashroff06-code/sentinel-gujarat"),
    ...plain("Demo video 1 (unlisted): ", "to be added at submission"),
    ...plain("Demo video 2 (unlisted): ", "to be added at submission"),
    ...plain("Hosted platform: ", "to be added at submission; evaluator credentials go on the submission form only"),
    ...plain("HLD (PDF): ", "deliverables/HLD.pdf in the repository", true),
  ], { x: 7.05, y: 2.05, w: 5.5, h: 2.7, fontFace: FONT, fontSize: 12, isTextBox: true, valign: "top", margin: 2, paraSpaceAfter: 6 });
  s.addText("Every link is opened from a private window before submission. The repository, its history, the videos and the screenshots are swept for credentials before submission.",
    { x: 7.05, y: 4.9, w: 5.5, h: 0.8, fontFace: FONT, fontSize: 10.5, italic: true, color: C.muted, isTextBox: true, margin: 0 });
  s.addText("Sentinel: one platform, five departments, watching is not storing.", { x: 7.05, y: 5.9, w: 5.5, h: 0.6, fontFace: FONT, fontSize: 13, bold: true, color: C.text, isTextBox: true, margin: 0 });
}

pres.writeFile({ fileName: path.join(__dirname, "..", "Sentinel-Solution-Presentation.pptx") })
  .then((f) => console.log("wrote", f));
