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
        if len(self.generated.tracks) != len(self.reference.tracks):
            top_div = f"Track count mismatch: {len(self.generated.tracks)} != {len(self.reference.tracks)}"
        else:
            for gt, rt in zip(self.generated.tracks, self.reference.tracks):
                if gt.name != rt.name:
                    top_div = f"Track name mismatch: {gt.name} != {rt.name}"
                    break
                # Compare tuning dicts
                gt_tuning = gt.tuning.model_dump()
                rt_tuning = rt.tuning.model_dump()
                if gt_tuning != rt_tuning:
                    top_div = f"Track tuning mismatch: {gt_tuning} != {rt_tuning}"
                    break

        if top_div is None:
            if len(self.generated.bars) != len(self.reference.bars):
                top_div = f"Bar count mismatch: {len(self.generated.bars)} != {len(self.reference.bars)}"
            else:
                for gb, rb in zip(self.generated.bars, self.reference.bars):
                    if gb.index != rb.index:
                        top_div = f"Bar index ordering mismatch: {gb.index} != {rb.index}"
                        break

        results["TOPOLOGY"] = LayerResult(
            layer="TOPOLOGY",
            passed=(top_div is None),
            first_divergence=top_div
        )

        # Helper to check if we should evaluate lower layers
        if not results["TOPOLOGY"].passed:
            for l in ["TAB_TOKEN", "OWNERSHIP", "ONSET", "RHYTHM", "MEASURE", "SCORE"]:
                results[l] = LayerResult(layer=l, passed=False, not_evaluated_reason="Blocked by TOPOLOGY divergence")
            return results

        # 2. MEASURE (Measure boundaries & structure)
        meas_div = None
        for i, (gb, rb) in enumerate(zip(self.generated.bars, self.reference.bars)):
            if gb.time_signature != rb.time_signature:
                meas_div = f"Bar {i+1} time signature mismatch"
                break

        results["MEASURE"] = LayerResult(
            layer="MEASURE",
            passed=(meas_div is None),
            first_divergence=meas_div
        )

        if not results["MEASURE"].passed:
            for l in ["TAB_TOKEN", "OWNERSHIP", "ONSET", "RHYTHM", "SCORE"]:
                results[l] = LayerResult(layer=l, passed=False, not_evaluated_reason="Blocked by MEASURE divergence")
            return results

        # Extract events
        gen_events = [e for b in self.generated.bars for e in b.events]
        ref_events = [e for b in self.reference.bars for e in b.events]

        # 3. SCORE (Overall event counts - aggregate counts cannot yield a pass when ordered events differ)
        score_div = None
        if len(gen_events) != len(ref_events):
            score_div = f"Total event count mismatch: {len(gen_events)} != {len(ref_events)}"

        results["SCORE"] = LayerResult(
            layer="SCORE",
            passed=(score_div is None),
            first_divergence=score_div
        )

        if not results["SCORE"].passed:
            for l in ["TAB_TOKEN", "OWNERSHIP", "ONSET", "RHYTHM"]:
                results[l] = LayerResult(layer=l, passed=False, not_evaluated_reason="Blocked by SCORE divergence")
            return results

        # Ordered event checks for lower layers
        token_div = None
        own_div = None
        onset_div = None
        rhy_div = None

        for i, (ge, re) in enumerate(zip(gen_events, ref_events)):
            # ONSET
            if ge.timing.onset_ticks != re.timing.onset_ticks or ge.timing.bar_index != re.timing.bar_index:
                onset_div = f"Event {i} onset timing mismatch"
                break

            # RHYTHM
            if ge.timing.notated_duration != re.timing.notated_duration:
                rhy_div = f"Event {i} rhythm duration mismatch"
                break

            # OWNERSHIP (Voice)
            if ge.timing.voice != re.timing.voice:
                own_div = f"Event {i} voice ownership mismatch"
                break

            # TAB_TOKEN (Strings and frets)
            g_notes = sorted((n.string, n.fret) for n in getattr(ge, 'notes', []))
            r_notes = sorted((n.string, n.fret) for n in getattr(re, 'notes', []))
            if g_notes != r_notes:
                token_div = f"Event {i} TAB token mismatch: {g_notes} != {r_notes}"
                break

        results["ONSET"] = LayerResult("ONSET", onset_div is None, first_divergence=onset_div)
        results["RHYTHM"] = LayerResult("RHYTHM", rhy_div is None, first_divergence=rhy_div)
        results["OWNERSHIP"] = LayerResult("OWNERSHIP", own_div is None, first_divergence=own_div)
        results["TAB_TOKEN"] = LayerResult("TAB_TOKEN", token_div is None, first_divergence=token_div)

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

