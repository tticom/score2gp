import subprocess
from pathlib import Path
import fitz  # type: ignore[import-not-found]

def generate_masked_image_for_omr(input_pdf: Path, out_img: Path) -> None:
    """
    Rasterizes the PDF to a PNG, detects tablature staves using our vector parser,
    and masks them out with white rectangles so that standard-notation OMR engines
    (like oemer or Audiveris) don't get confused by the 6-line staves.
    """
    from .pdf_staff_notation_diagnostics import extract_notation_diagnostics_dict
    from .pdf_staff_geometry import PdfStaffNotationGeometryDiagnostics

    doc = fitz.open(str(input_pdf))
    page = doc[0] # Just the first page for now, or loop pages if needed

    # Build diagnostics for this page (1-indexed)
    diags_dict = extract_notation_diagnostics_dict(page, 1)
    diags = PdfStaffNotationGeometryDiagnostics.model_validate(diags_dict)
    # The return is a pydantic model, convert to dict or access directly
    staves = getattr(diags, "staves", [])

    # 2. Draw white rectangles over any tablature staff
    for staff in staves:
        # Heuristic: Tablature usually has 6 lines
        staff_lines = getattr(staff, "staff_lines", [])
        if len(staff_lines) == 6:
            # Find the bounding box of the staff
            if staff_lines:
                min_y = min(line[1] for line in staff_lines)
                max_y = max(line[3] for line in staff_lines)
                # Extend horizontally across the whole page to erase the tab lines completely
                rect = fitz.Rect(0, min_y - 15, page.rect.width, max_y + 15)
                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))

    # 3. Render page to high-res image
    pix = page.get_pixmap(dpi=300)
    pix.save(str(out_img))
    doc.close()

def run_auto_omr(input_pdf: Path, out_dir: Path, audiveris_path: Path | None = None) -> Path:
    """
    Generates a MusicXML sidecar using Oemer (or Audiveris) after masking out tablature.
    Returns the path to the generated MusicXML file.
    """
    masked_img = out_dir / "masked_for_omr.png"
    generate_masked_image_for_omr(input_pdf, masked_img)

    if audiveris_path:
        log_path = out_dir / "auto_audiveris.log"
        # Convert PNG to PDF for audiveris? No, Audiveris can take PNG.
        subprocess.run(
            [str(audiveris_path), "-batch", "-export", "-output", str(out_dir), str(masked_img)],
            cwd=out_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        expected_mxl = out_dir / "masked_for_omr.mxl"
    else:
        # Fall back to Python native oemer library!
        log_path = out_dir / "auto_oemer.log"
        # Since oemer is installed in the local virtualenv, we need to provide the full path or use sys.executable
        import sys
        oemer_bin = str(Path(sys.executable).parent / "oemer")
        res = subprocess.run(
            [oemer_bin, str(masked_img.absolute())],
            cwd=out_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        if res.stdout or res.stderr:
            with open(log_path, "w") as f:
                f.write("STDOUT:\n")
                f.write(res.stdout)
                f.write("\nSTDERR:\n")
                f.write(res.stderr)
        # oemer outputs a .musicxml file alongside the image by default
        expected_mxl = out_dir / "masked_for_omr.musicxml"

    if expected_mxl.exists():
        return expected_mxl

    raise RuntimeError(f"OMR failed to generate {expected_mxl}. Check logs in {out_dir} for details.")
