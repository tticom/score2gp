#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
import fitz
import time

# List of all 12 corpus PDFs
PDF_FILES = [
    "Derek Trucks BB King.pdf",
    "Hal Leonard Corporation. Rock Ballads.pdf",
    "Jazz Classics for Solo Guitar- Chord Melody Arrangements.pdf",
    "Just-Practice-Like-THIS-Every-Day.pdf",
    "LegatoLicks.pdf",
    "Lesson-3.pdf",
    "Lesson-4.pdf",
    "Lesson-5.pdf",
    "Lesson-6.pdf",
    "Lesson-7.pdf",
    "Lick in All 5 CAGED Shapes start on the 5 _ guitar tab creator.pdf",
    "Melodic Soloing Masterclass.pdf"
]

def analyze_pdf(pdf_path: Path):
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    
    # Heuristic for born-digital vs scanned vs mixed
    has_text = False
    has_vector = False
    has_image = False
    
    for page in doc:
        if page.get_text().strip():
            has_text = True
        if page.get_drawings():
            has_vector = True
        if page.get_images():
            has_image = True
            
    if has_text and has_vector and not has_image:
        pdf_type = "born-digital"
    elif has_image and not has_text and not has_vector:
        pdf_type = "scanned"
    else:
        pdf_type = "mixed"
        
    return page_count, pdf_type

def run_conversion(
    pdf_name: str,
    corpus_dir: Path,
    out_dir: Path,
    timeout: int = 120,
    limit_pages: int = None,
    strict_mode: bool = False
):
    pdf_path = corpus_dir / pdf_name
    base_name = pdf_name[:-4]
    ref_gp_path = corpus_dir / f"{base_name}.gp"
    
    work_dir = out_dir / f"work_{base_name.replace(' ', '_')}"
    out_gp = out_dir / f"{base_name.replace(' ', '_')}.gp"
    json_report = out_dir / f"report_{base_name.replace(' ', '_')}.json"
    
    # Clean up old files if they exist to get a fresh run
    if out_gp.exists():
        out_gp.unlink()
    if json_report.exists():
        json_report.unlink()
        
    cmd = [
        sys.executable, "-m", "score2gp.cli", "convert",
        "--pdf", str(pdf_path),
        "--out", str(out_gp),
        "--work-dir", str(work_dir),
        "--json-report", str(json_report)
    ]
    
    # Default is strict mode. Bypassed with --no-strict unless strict_mode is True.
    used_no_strict = not strict_mode
    if used_no_strict:
        cmd.append("--no-strict")
    
    if ref_gp_path.exists():
        cmd.extend(["--ref-gp", str(ref_gp_path)])
        
    if limit_pages is not None:
        cmd.extend(["--pages", f"1-{limit_pages}"])
        
    print(f"Running conversion for: {pdf_name}...")
    
    status = "failed"
    exit_code = -1
    refusal_code = None
    stage = "unknown"
    error_msg = ""
    gp_written = False
    strict_ref_match = "None"
    semantic_diffs_str = ""
    timing_repair_used = False
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        exit_code = res.returncode
        error_msg = res.stderr or res.stdout
    except subprocess.TimeoutExpired as exc:
        status = "failed"
        exit_code = -1
        refusal_code = "timeout"
        stage = "unknown"
        error_msg = f"Timed out after {timeout} seconds"
        
    if json_report.exists():
        try:
            with open(json_report, "r", encoding="utf-8") as f:
                rep_data = json.load(f)
                status = rep_data.get("status", "failed")
                exit_code = rep_data.get("exit_code", exit_code)
                refusal_code = rep_data.get("refusal_code")
                stage = rep_data.get("stage", "unknown")
                gp_written = rep_data.get("output_written", False)
                timing_repair_used = rep_data.get("timing_repair_used", False)
                
                # Semantic comparison
                if ref_gp_path.exists():
                    sum_counts = rep_data.get("summary_counts", {})
                    sem_diffs = sum_counts.get("semantic_differences", {})
                    if status == "success" and not sem_diffs:
                        strict_ref_match = "Yes"
                        semantic_diffs_str = "None"
                    else:
                        strict_ref_match = "No"
                        if sem_diffs:
                            semantic_diffs_str = ", ".join(sem_diffs.keys())
                        else:
                            semantic_diffs_str = "Comparison Failed"
                else:
                    strict_ref_match = "None"
                    semantic_diffs_str = "N/A"
                    
                if rep_data.get("error_type"):
                    error_msg = f"{rep_data.get('error_type')}: {rep_data.get('recommended_action')}"
        except Exception as e:
            error_msg = f"Failed to parse json report: {e}"
            
    # Check if gp file was actually written if we don't have json report
    if not gp_written and out_gp.exists():
        gp_written = True
        
    return {
        "pdf_name": pdf_name,
        "ref_exists": ref_gp_path.exists(),
        "status": status,
        "exit_code": exit_code,
        "refusal_code": refusal_code,
        "stage": stage,
        "gp_written": gp_written,
        "strict_ref_match": strict_ref_match,
        "semantic_differences": semantic_diffs_str,
        "used_no_strict": used_no_strict,
        "timing_repair_used": timing_repair_used,
        "error_msg": error_msg.strip().split("\n")[0] if error_msg else ""
    }

def main():
    parser = argparse.ArgumentParser(description="Corpus Smoke Test Runner")
    parser.add_argument("--pdf", help="Only run on specific PDF file (e.g. Lesson-4.pdf)")
    parser.add_argument("--limit-pages", type=int, help="Limit page range processed per PDF (e.g. 2 for pages 1-2)")
    parser.add_argument("--timeout", type=int, default=120, help="Per-PDF timeout in seconds (default 120)")
    parser.add_argument("--strict", action="store_true", help="Run conversion in strict mode (fails on mismatch)")
    args = parser.parse_args()

    corpus_dir = Path("../score2gp-private-fixtures/fixtures/private")
    out_dir = Path("tmp/corpus_smoke")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_list = PDF_FILES
    if args.pdf:
        if args.pdf in PDF_FILES:
            pdf_list = [args.pdf]
        elif (corpus_dir / args.pdf).exists():
            pdf_list = [args.pdf]
        else:
            print(f"Error: Specified PDF file '{args.pdf}' not found in private fixtures.")
            sys.exit(1)
            
    results = []
    for pdf_name in pdf_list:
        pdf_path = corpus_dir / pdf_name
        if not pdf_path.exists():
            print(f"Skipping missing file: {pdf_name}")
            continue
            
        page_count, pdf_type = analyze_pdf(pdf_path)
        conv_res = run_conversion(
            pdf_name,
            corpus_dir,
            out_dir,
            timeout=args.timeout,
            limit_pages=args.limit_pages,
            strict_mode=args.strict
        )
        conv_res["page_count"] = page_count
        conv_res["pdf_type"] = pdf_type
        results.append(conv_res)
        
    # Generate markdown table with requested detailed columns
    md_lines = []
    md_lines.append("# Corpus Smoke Test Matrix")
    md_lines.append(f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')} | Strict Mode: {args.strict}\n")
    md_lines.append("| PDF Name | Pages | Type | Ref Available | Status | Exit Code | Stage | GP Written | Strict Ref Match | Semantic Diffs | Used No Strict | Timing Repair | Error / Refusal Code |")
    md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in results:
        ref_status = "Yes" if r["ref_exists"] else "No"
        status_icon = "🟢 PASS" if r["status"] == "success" else "🔴 FAIL"
        gp_written_str = "Yes" if r["gp_written"] else "No"
        ref_match_str = r["strict_ref_match"]
        diffs_str = r["semantic_differences"] or "None"
        used_no_strict_str = "Yes" if r["used_no_strict"] else "No"
        timing_repair_str = "Yes" if r["timing_repair_used"] else "No"
        err_msg = r["refusal_code"] or r["error_msg"] or "Unknown"
        md_lines.append(f"| {r['pdf_name']} | {r['page_count']} | {r['pdf_type']} | {ref_status} | {status_icon} | {r['exit_code']} | {r['stage']} | {gp_written_str} | {ref_match_str} | {diffs_str} | {used_no_strict_str} | {timing_repair_str} | {err_msg} |")
        
    report_md_path = out_dir / "corpus_smoke_matrix.md"
    report_md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nSmoke matrix written to {report_md_path}")
    
    # Also write JSON matrix
    report_json_path = out_dir / "corpus_smoke_matrix.json"
    report_json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    
if __name__ == "__main__":
    main()
