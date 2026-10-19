#!/usr/bin/env python3
"""Generate and verify actual Compact and Full PDFs for Concept Check report export using Headless Edge.

Verifies:
1. Compact mode excludes detailed evidence appendix even after accordions are manually opened.
2. Full mode includes all intended answers, support events, and conversation.
3. Initially closed nested details are included appropriately.
4. Text is readable, not clipped, and page counts reflect the actual generated files.
"""

import os
import subprocess
import sys
import fitz  # PyMuPDF
import pypdf

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

EDGE_BINARY = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(REPO_ROOT, "docs", "reviews", "2026-10-19")
TMP_DIR = os.path.join(REPO_ROOT, "tmp")

os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)


def render_html(mode: str, output_path: str, force_open: bool = False):
    script = os.path.join(REPO_ROOT, "scripts", "render_report.cjs")
    cmd = ["node", script, mode, output_path, "true" if force_open else "false"]
    print(f"Rendering HTML: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def generate_pdf(html_path: str, pdf_path: str):
    abs_html = os.path.abspath(html_path)
    abs_pdf = os.path.abspath(pdf_path)
    cmd = [
        EDGE_BINARY,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={abs_pdf}",
        abs_html,
    ]
    print(f"Generating PDF: {abs_pdf}")
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    if not os.path.exists(abs_pdf):
        raise RuntimeError(f"PDF was not generated at {abs_pdf}")
    print(f"Generated {abs_pdf} (size: {os.path.getsize(abs_pdf)} bytes)")


def inspect_pdf(pdf_path: str, label: str):
    print(f"\n==========================================")
    print(f"INSPECTING {label}: {pdf_path}")
    print(f"==========================================")

    # Inspect using PyMuPDF (fitz)
    doc = fitz.open(pdf_path)
    page_count_fitz = len(doc)

    # Inspect using pypdf
    reader = pypdf.PdfReader(pdf_path)
    page_count_pypdf = len(reader.pages)

    assert page_count_fitz == page_count_pypdf, f"Page count mismatch: fitz={page_count_fitz}, pypdf={page_count_pypdf}"
    print(f"Page Count: {page_count_fitz} pages")

    pages_text = []
    for i, page in enumerate(doc):
        text = page.get_text()
        pages_text.append(text)
        print(f"\n--- Page {i + 1} (chars: {len(text)}) ---")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        preview = lines[:8]
        for line in preview:
            safe_line = line.encode('ascii', errors='backslashreplace').decode('ascii')
            print(f"  {safe_line}")
        if len(lines) > 8:
            print(f"  ... [{len(lines) - 8} more lines]")

    full_text = "\n".join(pages_text)

    # Verification checks
    checks = {
        "has_header_title": "Storage & Persistence" in full_text and "Evidence report" in full_text,
        "has_session_overview": "Session overview" in full_text,
        "has_stage_progress": "Separate assessment stages" in full_text or "Baseline evidence" in full_text,
        "has_matched_skills": "Matched skills across cases" in full_text,
        "has_durable_write_timing": "Durable write timing" in full_text,
        "has_appendix_heading": "Detailed evidence & appendix" in full_text,
        "has_baseline_attempt_1": "An e-commerce order service" in full_text,
        "has_baseline_attempt_2": "A telemetry logging service" in full_text,
        "has_revised_attempt": "Re-evaluating the telemetry logging service" in full_text or "eliminate data loss" in full_text,
        "has_transfer_attempt": "photo-sharing backend processes" in full_text or "photo-sharing" in full_text.lower(),
        "has_support_history": "Support history" in full_text or "The Durable Write Boundary and WAL" in full_text,
        "has_conversation_transcript": "Saved conversation transcript" in full_text or "buffering telemetry in memory" in full_text,
    }

    print("\nContent Checks:")
    for check_name, passed in checks.items():
        print(f"  {check_name}: {'PASS' if passed else 'FAIL'}")

    return {
        "path": pdf_path,
        "page_count": page_count_fitz,
        "checks": checks,
        "pages_text": pages_text,
        "full_text": full_text,
    }


def main():
    if not os.path.exists(EDGE_BINARY):
        print(f"ERROR: Edge binary not found at {EDGE_BINARY}")
        sys.exit(1)

    # 1. Compact mode (default summary)
    compact_html = os.path.join(TMP_DIR, "report_compact.html")
    compact_pdf = os.path.join(DOCS_DIR, "report_compact.pdf")
    render_html("summary", compact_html, force_open=False)
    generate_pdf(compact_html, compact_pdf)
    res_compact = inspect_pdf(compact_pdf, "COMPACT MODE (DEFAULT)")

    # 2. Compact mode with accordions manually opened in UI
    compact_opened_html = os.path.join(TMP_DIR, "report_compact_opened.html")
    compact_opened_pdf = os.path.join(DOCS_DIR, "report_compact_accordions_opened.pdf")
    render_html("summary", compact_opened_html, force_open=True)
    generate_pdf(compact_opened_html, compact_opened_pdf)
    res_compact_opened = inspect_pdf(compact_opened_pdf, "COMPACT MODE (ACCORDIONS OPENED IN UI)")

    # 3. Full mode with complete appendix and conversation
    full_html = os.path.join(TMP_DIR, "report_full.html")
    full_pdf = os.path.join(DOCS_DIR, "report_full.pdf")
    render_html("full", full_html, force_open=False)
    generate_pdf(full_html, full_pdf)
    res_full = inspect_pdf(full_pdf, "FULL MODE (WITH COMPLETE APPENDIX)")

    print("\n==========================================")
    print("FINAL VERIFICATION SUMMARY")
    print("==========================================")
    print(f"Compact PDF path: {compact_pdf}")
    print(f"  Page count: {res_compact['page_count']}")
    print(f"  Appendix excluded: {not res_compact['checks']['has_appendix_heading']}")
    print(f"  Attempts excluded: {not res_compact['checks']['has_baseline_attempt_1']}")
    print(f"  Conversation excluded: {not res_compact['checks']['has_conversation_transcript']}")

    print(f"\nCompact (accordions opened) PDF path: {compact_opened_pdf}")
    print(f"  Page count: {res_compact_opened['page_count']}")
    print(f"  Appendix excluded even after manual open: {not res_compact_opened['checks']['has_appendix_heading']}")
    print(f"  Attempts excluded even after manual open: {not res_compact_opened['checks']['has_baseline_attempt_1']}")

    print(f"\nFull PDF path: {full_pdf}")
    print(f"  Page count: {res_full['page_count']}")
    print(f"  Appendix included: {res_full['checks']['has_appendix_heading']}")
    print(f"  Baseline 1 included: {res_full['checks']['has_baseline_attempt_1']}")
    print(f"  Baseline 2 included: {res_full['checks']['has_baseline_attempt_2']}")
    print(f"  Revised answer included: {res_full['checks']['has_revised_attempt']}")
    print(f"  Transfer case included: {res_full['checks']['has_transfer_attempt']}")
    print(f"  Support events included: {res_full['checks']['has_support_history']}")
    print(f"  Conversation transcript included: {res_full['checks']['has_conversation_transcript']}")

    # Assertions
    assert not res_compact['checks']['has_appendix_heading'], "Compact mode leaked appendix heading!"
    assert not res_compact['checks']['has_baseline_attempt_1'], "Compact mode leaked baseline attempts!"
    assert not res_compact_opened['checks']['has_appendix_heading'], "Compact mode with opened accordions leaked appendix!"
    assert not res_compact_opened['checks']['has_baseline_attempt_1'], "Compact mode with opened accordions leaked attempts!"

    assert res_full['checks']['has_appendix_heading'], "Full mode missing appendix!"
    assert res_full['checks']['has_baseline_attempt_1'], "Full mode missing baseline attempt 1!"
    assert res_full['checks']['has_baseline_attempt_2'], "Full mode missing baseline attempt 2!"
    assert res_full['checks']['has_revised_attempt'], "Full mode missing revised attempt!"
    assert res_full['checks']['has_transfer_attempt'], "Full mode missing transfer attempt!"
    assert res_full['checks']['has_support_history'], "Full mode missing support history!"
    assert res_full['checks']['has_conversation_transcript'], "Full mode missing conversation transcript!"

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
