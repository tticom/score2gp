import zipfile
import difflib
from pathlib import Path

def pretty_print_xml(xml_bytes):
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_bytes)
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="utf-8").decode("utf-8")
    except Exception:
        return xml_bytes.decode("utf-8", errors="replace")

def main():
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    private_dir = PROJECT_ROOT / "fixtures/private"
    smoke_dir = PROJECT_ROOT / "work/private_e2e_smoke_v0_1"
    out_dir = PROJECT_ROOT / "work/verification/relational_comparisons"
    
    out_dir.mkdir(parents=True, exist_ok=True)
    
    lessons = [3, 4, 5, 6, 7]
    
    for N in lessons:
        lesson_label = f"lesson_{N}"
        orig_gp_path = private_dir / f"Lesson-{N}.gp"
        gen_gp_path = smoke_dir / f"private_input_custom_lesson_{N}" / "smoke.gp"
        
        lesson_out = out_dir / lesson_label
        lesson_out.mkdir(parents=True, exist_ok=True)
        
        print(f"\nComparing Lesson {N}...")
        
        if not orig_gp_path.exists():
            print(f"  Original GP file not found: {orig_gp_path}")
            continue
        if not gen_gp_path.exists():
            print(f"  Generated GP file not found: {gen_gp_path}")
            continue
            
        # 1. Extract and pretty print original
        try:
            with zipfile.ZipFile(orig_gp_path, 'r') as zf:
                orig_raw = zf.read("Content/score.gpif")
                orig_pretty = pretty_print_xml(orig_raw)
                (lesson_out / "original.gpif").write_text(orig_pretty, encoding="utf-8")
        except Exception as e:
            print(f"  Error extracting original: {e}")
            continue
            
        # 2. Extract and pretty print generated
        try:
            with zipfile.ZipFile(gen_gp_path, 'r') as zf:
                gen_raw = zf.read("Content/score.gpif")
                gen_pretty = pretty_print_xml(gen_raw)
                (lesson_out / "generated.gpif").write_text(gen_pretty, encoding="utf-8")
        except Exception as e:
            print(f"  Error extracting generated: {e}")
            continue
            
        # 3. Generate standard unified diff
        orig_lines = orig_pretty.splitlines(keepends=True)
        gen_lines = gen_pretty.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            orig_lines,
            gen_lines,
            fromfile=f"Lesson-{N}-Original.gpif",
            tofile=f"Lesson-{N}-Generated.gpif",
            n=3
        )
        (lesson_out / "diff.txt").write_text("".join(diff), encoding="utf-8")
        
        # 4. Generate side-by-side HTML diff
        html_diff = difflib.HtmlDiff(wrapcolumn=80)
        html_content = html_diff.make_file(
            orig_lines,
            gen_lines,
            fromdesc=f"Lesson {N} - Original",
            todesc=f"Lesson {N} - Generated"
        )
        (lesson_out / "diff.html").write_text(html_content, encoding="utf-8")
        
        print(f"  Successfully wrote files to {lesson_out}")
        print(f"    - Original: original.gpif")
        print(f"    - Generated: generated.gpif")
        print(f"    - Plain Diff: diff.txt")
        print(f"    - Side-by-side HTML Diff: diff.html")

if __name__ == '__main__':
    main()
