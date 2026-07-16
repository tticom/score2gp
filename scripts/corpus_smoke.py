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

def parse_conversion_details(work_dir: Path, json_report: Path, out_gp: Path):
    timeline_available = "No"
    clef = "N/A"
    key = "N/A"
    meter = "N/A"
    confidence = 0.0
    measure_count = 0
    timing_valid = 0
    timing_invalid = 0
    
    # 1. Check if deterministic_omr.musicxml exists
    mxl_path = work_dir / "deterministic_omr.musicxml"
    if mxl_path.exists():
        timeline_available = "Yes"
        try:
            # Parse XML
            import xml.etree.ElementTree as ET
            tree = ET.parse(mxl_path)
            root = tree.getroot()
            measures = root.findall(".//measure")
            measure_count = len(measures)
            
            if measure_count > 0:
                first_measure = measures[0]
                clef = "Assumed G2" # Default fallback
                key = "0 fifths" # Default fallback
                meter = "Assumed 4/4" # Default fallback
                
                # Parse Clef
                clef_el = first_measure.find(".//clef")
                if clef_el is not None:
                    sign = clef_el.find("sign")
                    line = clef_el.find("line")
                    if sign is not None and line is not None:
                        clef = f"{sign.text}{line.text}"
                
                # Parse Key
                key_el = first_measure.find(".//key")
                if key_el is not None:
                    fifths = key_el.find("fifths")
                    if fifths is not None:
                        fifths_val = int(fifths.text)
                        key = f"{fifths_val} fifths"
                
                # Parse Time
                time_el = first_measure.find(".//time")
                if time_el is not None:
                    beats = time_el.find("beats")
                    beat_type = time_el.find("beat-type")
                    if beats is not None and beat_type is not None:
                        meter = f"{beats.text}/{beat_type.text}"
        except Exception as e:
            print(f"Error parsing MusicXML: {e}")
            
    # 2. Check timing valid/invalid from warnings.json
    warnings_json = work_dir / "warnings.json"
    if warnings_json.exists():
        try:
            with open(warnings_json, "r", encoding="utf-8") as f:
                warnings_data = json.load(f)
            
            invalid_measures = set()
            for w in warnings_data:
                if w.get("severity") == "error":
                    m_idx = w.get("measure_index")
                    if m_idx is not None:
                        invalid_measures.add(m_idx)
            
            timing_invalid = len(invalid_measures)
            timing_valid = max(0, measure_count - timing_invalid)
        except Exception as e:
            print(f"Error parsing warnings.json: {e}")
            
    # 3. Check score.ir.json for average confidence
    score_ir_path = work_dir / "score.ir.json"
    if score_ir_path.exists():
        try:
            with open(score_ir_path, "r", encoding="utf-8") as f:
                ir_data = json.load(f)
            confidences = []
            for bar in ir_data.get("bars", []):
                for event in bar.get("events", []):
                    if "confidence" in event:
                        confidences.append(event["confidence"])
            if confidences:
                confidence = sum(confidences) / len(confidences)
            else:
                confidence = 1.0
        except Exception as e:
            print(f"Error parsing score.ir.json: {e}")
            
    return {
        "timeline_available": timeline_available,
        "clef": clef,
        "key": key,
        "meter": meter,
        "confidence": round(confidence, 3),
        "measure_count": measure_count,
        "timing_valid": timing_valid,
        "timing_invalid": timing_invalid,
    }

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
        
    details = parse_conversion_details(work_dir, json_report, out_gp)
    
    res_dict = {
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
    res_dict.update(details)
    return res_dict

def is_inside_repo(path: Path) -> bool:
    resolved = path.resolve()
    for parent in [resolved] + list(resolved.parents):
        if (parent / ".git").exists():
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Corpus Smoke Test Runner")
    parser.add_argument("--pdf", help="Only run on specific PDF file (e.g. Lesson-4.pdf)")
    parser.add_argument("--limit-pages", type=int, help="Limit page range processed per PDF (e.g. 2 for pages 1-2)")
    parser.add_argument("--timeout", type=int, default=120, help="Per-PDF timeout in seconds (default 120)")
    parser.add_argument("--strict", action="store_true", help="Run conversion in strict mode (fails on mismatch)")
    parser.add_argument("--out-dir", required=True, help="Directory to write all conversion results (must not be inside repositories)")
    parser.add_argument("--corpus-dir", default="/home/tticom/work/score2gp-workspace/score2gp-private-fixtures/fixtures/private", help="Directory containing PDF files")
    args = parser.parse_args()

    corpus_dir = Path(args.corpus_dir)
    out_dir = Path(args.out_dir)
    
    if is_inside_repo(out_dir):
        print("Error: --out-dir must not be inside any git repository to prevent file pollution.")
        sys.exit(1)
        
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
    md_lines.append("| PDF Name | Type | Pages | Timeline Avail | Clef | Key | Meter | OMR Conf | Measures | Valid Meas | Invalid Meas | GP Written | Refusal Code | Evidence Summary |")
    md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in results:
        gp_written_str = "Yes" if r["gp_written"] else "No"
        ref_code = r["refusal_code"] or ("Success" if r["status"] == "success" else "Fail")
        evidence = r["error_msg"] or "N/A"
        md_lines.append(
            f"| {r['pdf_name']} | {r['pdf_type']} | {r['page_count']} | {r['timeline_available']} | "
            f"{r['clef']} | {r['key']} | {r['meter']} | {r['confidence']} | {r['measure_count']} | "
            f"{r['timing_valid']} | {r['timing_invalid']} | {gp_written_str} | {ref_code} | {evidence} |"
        )
        
    report_md_path = out_dir / "corpus_smoke_matrix.md"
    report_md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nSmoke matrix written to {report_md_path}")
    
    # Also write JSON matrix
    report_json_path = out_dir / "corpus_smoke_matrix.json"
    report_json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    
if __name__ == "__main__":
    main()
