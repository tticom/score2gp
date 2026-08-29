import subprocess
import sys
from pathlib import Path
from typing import Any, Optional
from enum import Enum, auto
import dataclasses

# Add src to pythonpath if not present
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from score2gp.gp_package import extract_score_ir_from_gp
from score2gp.ir import ScoreIR

class Layer(Enum):
    TOPOLOGY = auto()
    TAB_TOKEN = auto()
    OWNERSHIP = auto()
    ONSET = auto()
    RHYTHM = auto()
    MEASURE = auto()
    SCORE = auto()

@dataclasses.dataclass
class LayerResult:
    layer: str
    passed: bool
    not_evaluated_reason: Optional[str] = None
    first_divergence: Optional[str] = None

class LayeredSemanticOracle:
    def __init__(self, generated_ir: ScoreIR, reference_ir: ScoreIR):
        self.generated = generated_ir
        self.reference = reference_ir


    def evaluate(self) -> dict[str, LayerResult]:
        results = {}

        # 1. TOPOLOGY
        top_div = None
        if self.generated.tempo != self.reference.tempo:
            top_div = f"Global tempo mismatch: {self.generated.tempo} != {self.reference.tempo}"
        elif len(self.generated.tracks) != len(self.reference.tracks):
            top_div = f"Track count mismatch: {len(self.generated.tracks)} != {len(self.reference.tracks)}"
        else:
            for gt, rt in zip(self.generated.tracks, self.reference.tracks):
                if gt.name != rt.name:
                    top_div = f"Track name mismatch: {gt.name} != {rt.name}"
                    break
                if gt.tuning.model_dump() != rt.tuning.model_dump():
                    top_div = f"Track tuning mismatch: {gt.tuning.model_dump()} != {rt.tuning.model_dump()}"
                    break

        if top_div is None:
            if len(self.generated.bars) != len(self.reference.bars):
                top_div = f"Bar count mismatch: {len(self.generated.bars)} != {len(self.reference.bars)}"
            else:
                for gb, rb in zip(self.generated.bars, self.reference.bars):
                    if gb.index != rb.index:
                        top_div = f"Bar index ordering mismatch: {gb.index} != {rb.index}"
                        break

        results["TOPOLOGY"] = LayerResult("TOPOLOGY", passed=(top_div is None), first_divergence=top_div)

        # 2. MEASURE
        meas_div = None
        if top_div is None:
            for i, (gb, rb) in enumerate(zip(self.generated.bars, self.reference.bars)):
                if gb.time_signature != rb.time_signature:
                    meas_div = f"Bar {i+1} time signature mismatch"
                    break
                if gb.tempo != rb.tempo:
                    meas_div = f"Bar {i+1} local tempo mismatch"
                    break
        results["MEASURE"] = LayerResult("MEASURE", passed=(meas_div is None), first_divergence=meas_div)

        # 3. SCORE
        score_div = None
        gen_events = [e for b in self.generated.bars for e in b.events]
        ref_events = [e for b in self.reference.bars for e in b.events]
        if top_div is None and meas_div is None:
            if len(gen_events) != len(ref_events):
                score_div = f"Total event count mismatch: {len(gen_events)} != {len(ref_events)}"
        results["SCORE"] = LayerResult("SCORE", passed=(score_div is None), first_divergence=score_div)

        # Evaluate events for all lower layers simultaneously if SCORE passed
        token_div = None
        own_div = None
        onset_div = None
        rhy_div = None

        if top_div is None and meas_div is None and score_div is None:
            for i, (ge, re) in enumerate(zip(gen_events, ref_events)):
                if onset_div is None and (ge.timing.onset_ticks != re.timing.onset_ticks or ge.timing.bar_index != re.timing.bar_index):
                    onset_div = f"Event {i} onset timing mismatch"

                if rhy_div is None and (ge.timing.notated_duration != re.timing.notated_duration or getattr(ge.timing, 'duration_ticks', None) != getattr(re.timing, 'duration_ticks', None)):
                    rhy_div = f"Event {i} rhythm duration mismatch"

                if own_div is None and (ge.timing.voice != re.timing.voice or ge.track_id != re.track_id):
                    own_div = f"Event {i} track/voice ownership mismatch"

                if token_div is None:
                    g_notes = sorted((n.string, n.fret, getattr(n, 'pitch', None)) for n in getattr(ge, 'notes', []))
                    r_notes = sorted((n.string, n.fret, getattr(n, 'pitch', None)) for n in getattr(re, 'notes', []))
                    if g_notes != r_notes:
                        token_div = f"Event {i} TAB token/pitch mismatch: {g_notes} != {r_notes}"

        results["ONSET"] = LayerResult("ONSET", passed=(onset_div is None), first_divergence=onset_div)
        results["RHYTHM"] = LayerResult("RHYTHM", passed=(rhy_div is None), first_divergence=rhy_div)
        results["OWNERSHIP"] = LayerResult("OWNERSHIP", passed=(own_div is None), first_divergence=own_div)
        results["TAB_TOKEN"] = LayerResult("TAB_TOKEN", passed=(token_div is None), first_divergence=token_div)

        # Apply blocking cascade in strict order: TOPOLOGY -> MEASURE -> SCORE -> ONSET -> RHYTHM -> OWNERSHIP -> TAB_TOKEN
        ordered_layers = ["TOPOLOGY", "MEASURE", "SCORE", "ONSET", "RHYTHM", "OWNERSHIP", "TAB_TOKEN"]
        blocker = None
        for layer in ordered_layers:
            if blocker:
                results[layer] = LayerResult(layer=layer, passed=False, not_evaluated_reason=f"Blocked by {blocker} divergence")
            elif not results[layer].passed:
                blocker = layer

        return results

def run_isolated_generation(pdf_path: Path, output_gp_path: Path) -> None:
    """Run generation in a process that cannot receive reference GP paths or data."""
    cmd = [
        sys.executable, "-m", "score2gp.cli",
        "convert",
        "--pdf", str(pdf_path),
        "--out", str(output_gp_path),
        "--pdf-only-tab", "--no-strict", "--work-dir", str(output_gp_path.parent / "work")
    ]
    subprocess.run(cmd, check=True)


def evaluate_generation(pdf_path: Path, reference_gp_path: Path, output_gp_path: Path) -> dict[str, LayerResult]:
    if not pdf_path.exists() or not reference_gp_path.exists():
        return {"CORPUS": LayerResult("CORPUS", passed=False, not_evaluated_reason="Required source or reference artifacts are unavailable.")}

    if pdf_path.resolve() == reference_gp_path.resolve() or pdf_path.samefile(reference_gp_path):
        raise ValueError("Input and reference paths must not be aliased")

    if output_gp_path.exists():
        if reference_gp_path.resolve() == output_gp_path.resolve() or reference_gp_path.samefile(output_gp_path):
            raise ValueError("Reference and output paths must not be aliased")
        if pdf_path.resolve() == output_gp_path.resolve() or pdf_path.samefile(output_gp_path):
            raise ValueError("Input and output paths must not be aliased")
    else:
        # Check parent directory to ensure it doesn't resolve to the same as reference
        if reference_gp_path.resolve() == output_gp_path.resolve():
            raise ValueError("Reference and output paths must not be aliased")
        if pdf_path.resolve() == output_gp_path.resolve():
            raise ValueError("Input and output paths must not be aliased")

    run_isolated_generation(pdf_path, output_gp_path)

    gen_ir = extract_score_ir_from_gp(output_gp_path)
    ref_ir = extract_score_ir_from_gp(reference_gp_path)

    oracle = LayeredSemanticOracle(gen_ir, ref_ir)
    return oracle.evaluate()



import argparse
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Layered Semantic Oracle")
    parser.add_argument("--pdf", type=Path, required=True, help="Input PDF path")
    parser.add_argument("--ref", type=Path, required=True, help="Reference GP package path")
    parser.add_argument("--out", type=Path, required=True, help="Output GP package path")

    args = parser.parse_args()

    try:
        results = evaluate_generation(args.pdf, args.ref, args.out)

        output = {}
        for layer_name, result in results.items():
            output[layer_name] = {
                "passed": result.passed,
                "first_divergence": result.first_divergence,
                "not_evaluated_reason": result.not_evaluated_reason
            }

        print(json.dumps(output, indent=2))

        if not all(r.passed for r in results.values()):
            sys.exit(1)

    except Exception as e:
        print(f"Error during evaluation: {e}")
        sys.exit(2)
