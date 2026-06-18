#!/usr/bin/env bash

set -u

if [ ! -f "pyproject.toml" ]; then
  echo "ERROR: Run this script from the repo root: score2gp/"
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "ERROR: .venv/bin/python not found. Activate/create the venv first."
  exit 1
fi

PDF_DIR="fixtures/private/simple"
OUT_ROOT="work/private/note_type_experiment"
PY="./.venv/bin/python"

mkdir -p "$OUT_ROOT"

echo "Running editable-draft experiments..."

for pdf in WholeNote.pdf HalfNotes.pdf WholeNoteRest.pdf WholeNoteTab.pdf; do
  name="${pdf%.pdf}"
  input="$PDF_DIR/$pdf"
  out_dir="$OUT_ROOT/$name"

  echo ""
  echo "=== editable-draft: $pdf ==="

  if [ ! -f "$input" ]; then
    echo "MISSING: $input"
    continue
  fi

  mkdir -p "$out_dir"

  "$PY" -m score2gp.cli convert --pdf "$input" --template "fixtures/templates/minimal_gp7.gp" --out "$out_dir/output.gp" --work-dir "$out_dir" --json-report "$out_dir/report.json" --strict --editable-draft || true
done

echo ""
echo "Validating editable-draft outputs..."

for pdf in WholeNote.pdf HalfNotes.pdf WholeNoteRest.pdf WholeNoteTab.pdf; do
  name="${pdf%.pdf}"
  out_file="$OUT_ROOT/$name/output.gp"

  if [ -f "$out_file" ]; then
    echo ""
    echo "=== validate: $name ==="
    "$PY" -m score2gp.cli validate "$out_file" || true
  fi
done

echo ""
echo "Running pdf-only-tab experiment for WholeNoteTab.pdf..."

mkdir -p "$OUT_ROOT/WholeNoteTab_pdf_only_tab"

"$PY" -m score2gp.cli convert --pdf "$PDF_DIR/WholeNoteTab.pdf" --template "fixtures/templates/minimal_gp7.gp" --out "$OUT_ROOT/WholeNoteTab_pdf_only_tab/output.gp" --work-dir "$OUT_ROOT/WholeNoteTab_pdf_only_tab" --json-report "$OUT_ROOT/WholeNoteTab_pdf_only_tab/report.json" --strict --pdf-only-tab || true

if [ -f "$OUT_ROOT/WholeNoteTab_pdf_only_tab/output.gp" ]; then
  echo ""
  echo "=== validate: WholeNoteTab_pdf_only_tab ==="
  "$PY" -m score2gp.cli validate "$OUT_ROOT/WholeNoteTab_pdf_only_tab/output.gp" || true
fi

echo ""
echo "=== Report summaries ==="

"$PY" -c 'import json,pathlib; root=pathlib.Path("work/private/note_type_experiment"); reports=sorted(root.glob("*/report.json")); [print(p.parent.name, "status=", (d:=json.loads(p.read_text())).get("status"), "stage=", d.get("stage"), "events=", d.get("summary_counts",{}).get("event_count"), "bars=", d.get("summary_counts",{}).get("bar_count"), "rhythm=", d.get("pdf_only_diagnostics",{}).get("inferred_rhythm_status"), "warnings=", d.get("summary_counts",{}).get("warning_count")) for p in reports]'

echo ""
echo "=== Duration counts ==="

"$PY" -c 'import json,pathlib,collections; root=pathlib.Path("work/private/note_type_experiment"); files=sorted(root.glob("*/score.ir.json")); [print(p.parent.name, collections.Counter(e.get("timing",{}).get("notated_duration",{}).get("value") for b in json.loads(p.read_text()).get("bars",[]) for e in b.get("events",[]))) for p in files]'

echo ""
echo "=== Timing/default/rhythm warnings ==="

"$PY" -c 'import json,pathlib; root=pathlib.Path("work/private/note_type_experiment"); files=sorted(root.glob("*/warnings.json")); [print("\n"+p.parent.name+"\n"+"\n".join((w.get("code","")+" :: "+w.get("message","")) for w in json.loads(p.read_text()) if "timing" in w.get("code","").lower() or "default" in w.get("message","").lower() or "rhythm" in w.get("message","").lower())) for p in files]'

echo ""
echo "Done."
