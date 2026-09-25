"""Render deliverables/HLD.md -> HLD.html (scratch) -> deliverables/HLD.pdf.

pandoc (Anaconda) converts GFM to an HTML body; this script wraps it with
print CSS and prints it with Playwright's Chromium (project venv).
Usage: .venv/Scripts/python scripts/render_hld.py [<repo root> [<scratch dir> [<doc>]]]
(defaults: this repo, a temporary directory for the intermediate HTML, and
HLD.md). <doc> is any Markdown file in deliverables/ - S5.5 renders
departmental-systems-unaffected.md the same way; the PDF takes the doc's
stem and the footer its first "# " heading. SENTINEL_PANDOC overrides the
pandoc path (default: Anaconda's).
Written by the S5.1 session on 25 Sep; committed so a re-render after an
HLD edit needs nothing outside the repo.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

import tempfile

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
SCRATCH = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tempfile.mkdtemp(prefix="hld-"))
DOC = sys.argv[3] if len(sys.argv) > 3 else "HLD.md"
PANDOC = os.environ.get("SENTINEL_PANDOC", r"D:\Anaconda\Library\bin\pandoc.exe")

CSS = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Segoe UI", "Nirmala UI", Arial, sans-serif; font-size: 9.6pt;
       line-height: 1.42; color: #16202b; margin: 0; }
h1 { font-size: 20pt; margin: 0 0 4pt 0; color: #0b2545; }
h2 { font-size: 13.5pt; margin: 16pt 0 5pt 0; color: #0b2545;
     border-bottom: 1.2pt solid #0b2545; padding-bottom: 2pt; break-after: avoid; }
h3 { font-size: 11pt; margin: 11pt 0 4pt 0; color: #13315c; break-after: avoid; }
p { margin: 4pt 0 6pt 0; }
ul, ol { margin: 3pt 0 6pt 0; padding-left: 16pt; }
li { margin: 1.5pt 0; }
hr { border: 0; border-top: 0.6pt solid #b8c2cc; margin: 10pt 0; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.8pt;
       background: #eef1f4; padding: 0 2pt; border-radius: 2pt; }
pre { font-family: Consolas, "Courier New", monospace; font-size: 8.3pt;
      line-height: 1.22; white-space: pre; overflow: visible; background: #f5f7f9;
      border: 0.6pt solid #c9d1d9; padding: 7pt 8pt; margin: 6pt 0 8pt 0;
      break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0 9pt 0; font-size: 8.7pt;
        line-height: 1.32; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { background: #0b2545; color: #fff; text-align: left; font-weight: 600;
     padding: 3pt 5pt; border: 0.6pt solid #0b2545; }
td { padding: 3pt 5pt; border: 0.6pt solid #c9d1d9; vertical-align: top;
     overflow-wrap: break-word; }
td:first-child { min-width: 22mm; }
tbody tr:nth-child(even) td { background: #f5f7f9; }
blockquote { margin: 6pt 0; padding: 4pt 9pt; border-left: 3pt solid #13315c;
             background: #eef3f8; }
blockquote p { margin: 2pt 0; }
strong { color: #0b2545; }
th strong, th em, th code { color: inherit; background: none; }
"""

FOOTER = (
    '<div style="width:100%;font-size:7.5pt;color:#6b7785;'
    'font-family:Segoe UI,Arial,sans-serif;padding:0 15mm;display:flex;'
    'justify-content:space-between;">'
    '<span>{label}, revised 25 Sep 2026</span>'
    '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>'
    "</div>"
)


def doc_title(md_text: str) -> str:
    """The first ``# `` heading, for the HTML title and the footer.
    Returns "Sentinel - Technical Proposal (HLD)" for the HLD (its footer
    wording since S5.1), else "Sentinel - <heading>"; never raises."""
    for line in md_text.splitlines():
        if line.startswith("# "):
            heading = line[2:].strip().replace("Sentinel: ", "")
            if heading.startswith("Technical Proposal"):
                return "Sentinel - Technical Proposal (HLD)"
            return f"Sentinel - {heading}"
    return "Sentinel"


def main() -> None:
    md = ROOT / "deliverables" / DOC
    label = doc_title(md.read_text(encoding="utf-8"))
    body = subprocess.run(
        [PANDOC, "-f", "gfm", "-t", "html5", str(md)],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>{label}</title>"
        f"<style>{CSS}</style></head><body>{body}</body></html>"
    )
    out_html = SCRATCH / f"{md.stem}.html"
    out_html.write_text(html, encoding="utf-8")
    out_pdf = ROOT / "deliverables" / f"{md.stem}.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(out_html.as_uri())
            page.pdf(
                path=str(out_pdf), format="A4", print_background=True,
                display_header_footer=True, header_template="<div></div>",
                footer_template=FOOTER.format(label=label),
                prefer_css_page_size=True,
            )
        finally:
            browser.close()
    print(f"wrote {out_html} and {out_pdf} ({out_pdf.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
